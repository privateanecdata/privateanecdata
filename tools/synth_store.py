"""
Create a synthetic submission store for testing the release pipeline. Writes rows exactly the way
app/src/lib/db.ts does — random 62-bit rowid, per-row 32-byte salt, Merkle leaf in the same
transaction — so verify_release.py and release.py exercise the real code path.

    python3 tools/synth_store.py /tmp/synth.db --n 3000 --seed 1
    python3 tools/synth_store.py /tmp/synth.db --n 200 --seed 2 --append --day 2026-12-15

Never point this at the real store. It refuses to append to a database it did not create.
"""
import argparse
import datetime as dt
import json
import os
import random
import sqlite3
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from pa_store import ROW_FIELDS, canonical_json, leaf_hash  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
TAX = os.path.join(HERE, "..", "spec", "taxonomy.v1.json")

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS reports (
  rowid INTEGER PRIMARY KEY, received_day TEXT NOT NULL, schema_version TEXT NOT NULL,
  compound TEXT NOT NULL, route TEXT NOT NULL, goal TEXT, source_channel TEXT NOT NULL,
  start_dose TEXT, current_dose TEXT, frequency TEXT NOT NULL,
  duration TEXT NOT NULL, purity_tested TEXT NOT NULL,
  status TEXT NOT NULL, stop_reason TEXT, outcome TEXT, adverse_effects TEXT NOT NULL,
  age_band TEXT, sex TEXT, salt BLOB NOT NULL);
CREATE TABLE IF NOT EXISTS merkle_leaves (idx INTEGER PRIMARY KEY AUTOINCREMENT, leaf BLOB NOT NULL);
CREATE TABLE IF NOT EXISTS exclusions (leaf_idx INTEGER PRIMARY KEY, reason TEXT NOT NULL, noted_on TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS _synthetic (marker TEXT);
"""


def zipf(n, s=1.0):
    w = [1 / (i + 1) ** s for i in range(n)]
    t = sum(w)
    return [x / t for x in w]


def pick(rng, options, weights=None):
    return rng.choices(options, weights=weights, k=1)[0]


def ids(opts):
    return [o["id"] for o in opts]


def gen_row(rng, tax, day, compound=None, goal=None):
    sh = tax["shared"]
    compounds = tax["compounds"]
    # Compound popularity: Zipf over a shuffled-but-seeded order so the skew is stable per seed.
    if compound:
        c = next(x for x in compounds if x["id"] == compound)
    else:
        c = pick(rng, compounds, zipf(len(compounds), 0.9)) if rng.random() > 0.02 else None
    if c is None:
        # "Other (not listed)": counted, never broken out.
        route = pick(rng, ids(tax["routes"]))
        row = dict(compound="other", route=route, goal=None, start_dose=None, current_dose=None,
                   frequency=pick(rng, ids(tax["frequency"])), outcome=None)
        ae_pool = [a["id"] for a in tax["universalAdverseEffects"]]
    else:
        route = pick(rng, c["routes"], zipf(len(c["routes"]), 1.2))
        nb = len(c["doseBands"])
        start = rng.choices(range(nb), weights=[max(1, 4 - abs(i - nb // 3)) for i in range(nb)])[0] if nb else None
        row = dict(
            compound=c["id"], route=route,
            goal=goal if goal in c["goals"] else pick(rng, c["goals"] + ["other"], zipf(len(c["goals"]) + 1, 1.0)),
            start_dose=f"b{start}" if nb else None,
            current_dose=None,
            frequency=pick(rng, c["frequency"] + ["other"], zipf(len(c["frequency"]) + 1, 1.0)),
            outcome=pick(rng, ids(sh["outcome"]), [0.35, 0.3, 0.25, 0.1]),
        )
        own = c["adverseEffects"]
        uni = [a["id"] for a in tax["universalAdverseEffects"]]
        inj = route in ("subcutaneous", "intramuscular", "intravenous")
        uni = [a for a in uni if (a != "injection-site" or inj) and (a != "nasal-irritation" or route == "intranasal")]
        ae_pool = uni + own
    # Current dose: most stay put, some step up, a few step down.
    if row["start_dose"] is not None:
        s = int(row["start_dose"][1:])
        move = pick(rng, [0, 1, 2, -1], [0.55, 0.28, 0.07, 0.10])
        row["current_dose"] = f"b{min(nb - 1, max(0, s + move))}"
    row["source_channel"] = pick(rng, ids(sh["sourceChannel"]), [0.05, 0.15, 0.2, 0.3, 0.2, 0.05, 0.03, 0.02])
    row["duration"] = pick(rng, ids(sh["duration"]), [0.1, 0.2, 0.3, 0.2, 0.12, 0.08])
    row["purity_tested"] = pick(rng, ids(sh["purityTested"]), [0.7, 0.15, 0.05, 0.05, 0.05])
    dur_wk = {"under-2wk": (0, 2), "2-4wk": (2, 4), "1-3mo": (4, 13), "3-6mo": (13, 26), "6-12mo": (26, 52), "over-12mo": (52, 999)}[row["duration"]]
    row["status"] = pick(rng, ["still-taking", "completed-planned-course", "stopped"], [0.4, 0.15, 0.45])
    # Adverse effects: 45% none; otherwise 1–3 from the pool, each with onset and dechallenge
    # consistent with duration and status.
    effects = []
    if rng.random() > 0.45 and ae_pool:
        k = rng.choices([1, 2, 3], weights=[0.6, 0.3, 0.1])[0]
        pool = [a for a in ae_pool if a != "no-effect" or row["outcome"] in (None, "no-change", "slight")]
        for aid in rng.sample(pool, min(k, len(pool))):
            still = row["status"] == "still-taking"
            dech = pick(rng, ["still-taking", "unsure"], [0.9, 0.1]) if still else pick(rng, ["resolved", "did-not-resolve", "unsure"], [0.6, 0.25, 0.15])
            onsets = [o for o, lo in {"first-days": 0, "first-2wk": 0, "2-6wk": 2, "after-6wk": 6, "unsure": 0}.items() if lo <= dur_wk[1]]
            effects.append({"id": aid, "onset": pick(rng, onsets), "dechallenge": dech})
    row["adverse_effects"] = json.dumps(effects, separators=(",", ":"))
    if row["status"] == "stopped":
        reasons, w = ids(sh["stopReason"]), [0.25, 0.3, 0.15, 0.1, 0.1, 0.05, 0.05]
        if not effects:
            w = [x if r != "adverse-effect" else 0 for r, x in zip(reasons, w)]
        row["stop_reason"] = pick(rng, reasons, w)
    else:
        row["stop_reason"] = None
    row["age_band"] = pick(rng, ids(sh["ageBand"]) + [None], [0.08, 0.25, 0.28, 0.18, 0.08, 0.03, 0.1])
    row["sex"] = pick(rng, ids(sh["sex"]) + [None], [0.30, 0.52, 0.01, 0.02, 0.05, 0.10])
    row["received_day"] = day
    row["schema_version"] = tax["version"]
    return {k: row[k] for k in ROW_FIELDS}


def insert(con, rng, row):
    salt = rng.randbytes(32)
    leaf = leaf_hash(salt, canonical_json(row))
    rowid = int.from_bytes(rng.randbytes(8), "big") & 0x3FFFFFFFFFFFFFFF
    cols = ", ".join(ROW_FIELDS)
    qs = ", ".join("?" for _ in ROW_FIELDS)
    with con:
        con.execute(f"INSERT INTO reports (rowid, {cols}, salt) VALUES (?, {qs}, ?)", [rowid, *[row[k] for k in ROW_FIELDS], salt])
        con.execute("INSERT INTO merkle_leaves (leaf) VALUES (?)", [leaf])


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("db")
    ap.add_argument("--n", type=int, default=2000)
    ap.add_argument("--seed", type=int, default=20260912)
    ap.add_argument("--append", action="store_true", help="add rows to an existing synthetic store")
    ap.add_argument("--day", help="single received_day for all rows (default: spread over 90 days ending today)")
    ap.add_argument("--taxonomy", default=TAX)
    ap.add_argument("--contradictions", type=int, default=0, help="deliberately break a rule in this many rows (detector test)")
    ap.add_argument("--compound", help="put every generated row on this compound id (update-floor tests)")
    ap.add_argument("--goal", help="with --compound: give every generated row this goal id")
    args = ap.parse_args()

    tax = json.load(open(args.taxonomy))
    rng = random.Random(args.seed)
    exists = os.path.exists(args.db)
    if exists and not args.append:
        sys.exit(f"{args.db} exists; pass --append to add rows, or remove it")
    con = sqlite3.connect(args.db)
    if exists:
        if not con.execute("SELECT name FROM sqlite_master WHERE name='_synthetic'").fetchone():
            sys.exit("refusing to append: this store was not created by synth_store.py")
    else:
        con.executescript(SCHEMA_SQL)
        con.execute("INSERT INTO _synthetic VALUES ('synthetic store — never publish')")
        con.commit()
    end = dt.date.today()
    for i in range(args.n):
        day = args.day or (end - dt.timedelta(days=int(rng.betavariate(1.2, 2.5) * 90))).isoformat()
        row = gen_row(rng, tax, day, args.compound, args.goal)
        if i < args.contradictions:
            row["duration"] = "under-2wk"
            row["adverse_effects"] = json.dumps([{"id": "headache", "onset": "after-6wk", "dechallenge": "unsure"}], separators=(",", ":"))
        insert(con, rng, row)
    n = con.execute("SELECT COUNT(*) FROM reports").fetchone()[0]
    print(f"{args.db}: {n} rows, {con.execute('SELECT COUNT(*) FROM merkle_leaves').fetchone()[0]} leaves")


if __name__ == "__main__":
    main()
