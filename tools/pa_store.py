"""
Read-only access to the submission store for the release tools, plus a byte-exact Python mirror
of app/src/lib/merkle.ts so the log can be recomputed and checked outside the app.

Nothing here writes to the store. synth_store.py is the only tool that does, and only to a store
it creates itself.
"""
import hashlib
import json
import sqlite3
from collections import Counter

# The stored row, exactly the columns that are hashed into the leaf (everything except rowid and salt).
ROW_FIELDS = [
    "received_day", "schema_version", "compound", "route", "goal", "source_channel",
    "start_dose", "current_dose", "frequency", "duration", "purity_tested",
    "status", "stop_reason", "outcome", "adverse_effects", "age_band", "sex",
]


# ---------------------------------------------------------------- merkle (mirror of merkle.ts)

def canonical_json(row: dict) -> str:
    """Same bytes as JSON.stringify over sorted keys: no spaces, non-ASCII left raw."""
    return json.dumps({k: row[k] for k in sorted(row)}, separators=(",", ":"), ensure_ascii=False)


def leaf_hash(salt: bytes, canonical: str) -> bytes:
    return hashlib.sha256(salt + canonical.encode("utf-8")).digest()


def merkle_root(leaves) -> bytes:
    """RFC 6962-style: interior = SHA-256(0x01 || left || right); an odd leaf is promoted."""
    if not leaves:
        return hashlib.sha256(b"").digest()
    level = list(leaves)
    while len(level) > 1:
        nxt = []
        for i in range(0, len(level), 2):
            if i + 1 < len(level):
                nxt.append(hashlib.sha256(b"\x01" + level[i] + level[i + 1]).digest())
            else:
                nxt.append(level[i])
        level = nxt
    return level[0]


# ---------------------------------------------------------------- store

def open_store(path: str) -> sqlite3.Connection:
    con = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    return con


def load_rows(con) -> list:
    """Every stored row as a dict of ROW_FIELDS plus '_salt' (bytes). Order is not meaningful."""
    cols = ", ".join(ROW_FIELDS)
    out = []
    for r in con.execute(f"SELECT {cols}, salt FROM reports"):
        row = {k: r[k] for k in ROW_FIELDS}
        row["_salt"] = bytes(r["salt"])
        out.append(row)
    return out


def load_leaves(con) -> list:
    """Leaves in log order, as (idx, bytes)."""
    return [(r["idx"], bytes(r["leaf"])) for r in con.execute("SELECT idx, leaf FROM merkle_leaves ORDER BY idx")]


def load_exclusions(con) -> list:
    return [dict(r) for r in con.execute("SELECT leaf_idx, reason, noted_on FROM exclusions ORDER BY leaf_idx")]


def row_leaf(row: dict) -> bytes:
    data = {k: row[k] for k in ROW_FIELDS}
    return leaf_hash(row["_salt"], canonical_json(data))


def verify_store(rows: list, leaves: list) -> dict:
    """
    Recompute every row's leaf and check the multiset equals the stored log. This detects an
    altered, added or removed row without needing any link between rows and log positions —
    there is none by design.
    """
    recomputed = Counter(row_leaf(r) for r in rows)
    stored = Counter(l for _, l in leaves)
    missing = list((recomputed - stored).elements())   # rows whose hash is not in the log
    orphans = list((stored - recomputed).elements())   # leaves with no matching row
    root = merkle_root([l for _, l in leaves])
    return {
        "ok": not missing and not orphans and len(rows) == len(leaves),
        "rows": len(rows),
        "leaves": len(leaves),
        "rows_not_in_log": len(missing),
        "leaves_without_row": len(orphans),
        "root": root.hex(),
    }


def attach_leaf_idx(rows: list, leaves: list) -> None:
    """Sets row['_leaf_idx'] by matching recomputed hashes. Operator-side only; never published."""
    by_leaf = {}
    for idx, leaf in leaves:
        by_leaf.setdefault(leaf, []).append(idx)
    for r in rows:
        lst = by_leaf.get(row_leaf(r))
        r["_leaf_idx"] = lst.pop(0) if lst else None
