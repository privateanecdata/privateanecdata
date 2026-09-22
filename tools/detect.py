#!/usr/bin/env python3
"""
Quality detector. Scans the store and proposes exclusions; a person decides.

    python3 tools/detect.py scan  --db data/reports.db --out candidates.json [--since 2026-10-01]
    python3 tools/detect.py apply --db data/reports.db candidates.json --date 2026-12-20

`scan` writes candidates as {leaf_idx, reason, rule, evidence}. Nothing is excluded until
`apply` writes the reviewed file into the store's `exclusions` table. Excluded reports stay in the
Merkle log; they are omitted from tables and listed, by log position and reason code, in every
release from then on (RELEASE_SPEC.md, Exclusions).

Rules are deliberately conservative: each flags a contradiction inside a single report, or a
pattern across reports that a person should look at. The detector never uses network metadata —
there is none — and never looks at anything but the stored fields.

Reason codes: malformed · implausible · duplicate-pattern · coordinated · test

The candidates file and the `evidence` strings contain field values of individual reports. It is
an operator working file: keep it with the store, never publish it, delete it after apply.
"""
import argparse
import datetime as dt
import json
import os
import sqlite3
import sys
from collections import Counter, defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from pa_store import ROW_FIELDS, attach_leaf_idx, load_exclusions, load_leaves, load_rows, open_store  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
TAX = os.path.join(HERE, "..", "spec", "taxonomy.v1.json")

# Week ranges implied by the vocabularies; two answers contradict when their ranges cannot overlap.
DURATION_WEEKS = {"under-2wk": (0, 2), "2-4wk": (2, 4), "1-3mo": (4, 13), "3-6mo": (13, 26), "6-12mo": (26, 52), "over-12mo": (52, 999)}
STOPPED_WEEKS = {"stopped-under-2wk": (0, 2), "stopped-2-6wk": (2, 6), "stopped-6-12wk": (6, 12), "stopped-over-12wk": (12, 999)}
ONSET_MIN_WEEKS = {"first-days": 0, "first-2wk": 0, "2-6wk": 2, "after-6wk": 6}


def overlaps(a, b):
    return a[0] <= b[1] and b[0] <= a[1]


def band_index(v):
    return int(v[1:]) if v and v.startswith("b") and v[1:].isdigit() else None


class Tax:
    def __init__(self, path):
        raw = json.load(open(path))
        self.compounds = {c["id"]: c for c in raw["compounds"]}
        self.shared = {k: {o["id"] for o in v} for k, v in raw["shared"].items()}
        self.routes = {o["id"] for o in raw["routes"]}
        self.frequency = {o["id"] for o in raw["frequency"]}
        self.universal_ae = {o["id"] for o in raw["universalAdverseEffects"]}


# ---------------------------------------------------------------- per-row rules

def check_malformed(r, tax):
    """Values outside the vocabulary the form would have offered. The server validates these, so
    a hit here means the store was written by something other than the form."""
    c = tax.compounds.get(r["compound"])
    other = r["compound"] == "other"
    if not c and not other:
        return f"unknown compound {r['compound']!r}"
    if r["route"] not in (c["routes"] if c else tax.routes):
        return f"route {r['route']!r} not offered for {r['compound']}"
    if c and r["goal"] not in set(c["goals"]) | {"other"}:
        return f"goal {r['goal']!r} not offered"
    if r["source_channel"] not in tax.shared["sourceChannel"]:
        return "bad source_channel"
    nb = len(c["doseBands"]) if c else 0
    for f in ("start_dose", "current_dose"):
        v = r[f]
        if c and (band_index(v) is None or band_index(v) >= nb):
            return f"{f} {v!r} outside {nb} bands"
        if other and v is not None:
            return f"{f} set for 'other' compound"
    if r["frequency"] not in (set(c["frequency"]) | {"other"} if c else tax.frequency):
        return "bad frequency"
    for f, key in (("titration", "titration"), ("duration", "duration"), ("purity_tested", "purityTested"),
                   ("reconstitution", "reconstitution"), ("status", "status")):
        if r[f] not in tax.shared[key]:
            return f"bad {f}"
    stopped = r["status"].startswith("stopped-")
    if stopped and r["stop_reason"] not in tax.shared["stopReason"]:
        return "stopped without a valid stop_reason"
    if not stopped and r["stop_reason"] is not None:
        return "stop_reason set but not stopped"
    if c and r["outcome"] not in tax.shared["outcome"]:
        return "bad outcome"
    try:
        effects = json.loads(r["adverse_effects"])
        assert isinstance(effects, list)
    except Exception:
        return "adverse_effects is not a JSON list"
    allowed = tax.universal_ae | (set(c["adverseEffects"]) if c else set())
    seen = set()
    for e in effects:
        if not isinstance(e, dict) or e.get("id") not in allowed:
            return f"effect {e!r} not offered"
        if e["id"] in seen:
            return f"effect {e['id']} listed twice"
        seen.add(e["id"])
        if e.get("onset") not in tax.shared["onset"] or e.get("dechallenge") not in tax.shared["dechallenge"]:
            return f"effect {e['id']} missing onset/dechallenge"
    if r["age_band"] is not None and r["age_band"] not in tax.shared["ageBand"]:
        return "bad age_band"
    if r["sex"] is not None and r["sex"] not in tax.shared["sex"]:
        return "bad sex"
    return None


def check_implausible(r):
    """Contradictions between two answers in the same report."""
    out = []
    dur = DURATION_WEEKS.get(r["duration"])
    st = STOPPED_WEEKS.get(r["status"])
    if dur and st and not overlaps(dur, st):
        out.append(f"duration {r['duration']} cannot contain status {r['status']}")
    effects = json.loads(r["adverse_effects"])
    stopped = r["status"] != "still-taking"
    for e in effects:
        lo = ONSET_MIN_WEEKS.get(e.get("onset"))
        if lo is not None and dur and lo > dur[1]:
            out.append(f"effect {e['id']} onset {e['onset']} after total duration {r['duration']}")
        if e.get("dechallenge") == "still-taking" and stopped:
            out.append(f"effect {e['id']}: 'haven't stopped' but status is {r['status']}")
        if e.get("dechallenge") in ("resolved", "did-not-resolve") and not stopped:
            out.append(f"effect {e['id']}: dechallenge reported but status is still-taking")
    if r["stop_reason"] == "adverse-effect" and not effects:
        out.append("stopped for side effects but reported none")
    if any(e["id"] == "no-effect" for e in effects) and r["outcome"] in ("moderate", "large"):
        out.append(f"'no noticeable effect at all' with outcome {r['outcome']}")
    s, c = band_index(r["start_dose"]), band_index(r["current_dose"])
    if s is not None and c is not None:
        if r["titration"] == "no-change" and s != c:
            out.append("titration no-change but dose bands differ")
        if r["titration"] == "stepped-up" and c < s:
            out.append("stepped-up but current band below start")
        if r["titration"] == "stepped-down" and c > s:
            out.append("stepped-down but current band above start")
    return out


# ---------------------------------------------------------------- cross-row rules

def check_duplicates(rows, min_identical=5):
    """Identical rows (every field) received on the same day, at or above a count that is unlikely
    for a coarsened row. Coarsening makes some identical rows expected; a burst of them is not."""
    key = lambda r: tuple(r[f] for f in ROW_FIELDS)
    groups = defaultdict(list)
    for r in rows:
        groups[key(r)].append(r)
    out = []
    for k, rs in groups.items():
        if len(rs) >= min_identical:
            for r in rs:
                out.append((r, f"{len(rs)} identical reports on {r['received_day']} ({r['compound']})"))
    return out


def check_coordinated(rows, min_day=20, ratio=5.0):
    """A day on which one compound's reports exceed both a floor and a multiple of that
    compound's median daily count over the previous four weeks."""
    per = defaultdict(Counter)   # compound -> day -> n
    for r in rows:
        per[r["compound"]][r["received_day"]] += 1
    out, patterns = [], []
    for comp, days in per.items():
        for day, n in days.items():
            if n < min_day:
                continue
            d = dt.date.fromisoformat(day)
            prev = [days.get((d - dt.timedelta(days=i)).isoformat(), 0) for i in range(1, 29)]
            med = sorted(prev)[len(prev) // 2]
            if n >= max(min_day, ratio * max(med, 1)):
                patterns.append({"compound": comp, "day": day, "n": n, "median_prev_28d": med})
                for r in rows:
                    if r["compound"] == comp and r["received_day"] == day:
                        out.append((r, f"{n} reports on {day} vs median {med}/day over prior 28 days"))
    return out, patterns


# ---------------------------------------------------------------- commands

def scan(args):
    tax = Tax(args.taxonomy)
    con = open_store(args.db)
    rows, leaves = load_rows(con), load_leaves(con)
    attach_leaf_idx(rows, leaves)
    already = {x["leaf_idx"] for x in load_exclusions(con)}
    if args.since:
        rows = [r for r in rows if r["received_day"] >= args.since]
    cands = {}

    def add(r, reason, rule, evidence):
        if r["_leaf_idx"] is None or r["_leaf_idx"] in already:
            return
        cands.setdefault(r["_leaf_idx"], {"leaf_idx": r["_leaf_idx"], "reason": reason, "rule": rule, "evidence": []})
        cands[r["_leaf_idx"]]["evidence"].append(evidence)

    for r in rows:
        m = check_malformed(r, tax)
        if m:
            add(r, "malformed", "vocabulary", m)
            continue
        for ev in check_implausible(r):
            add(r, "implausible", "contradiction", ev)
    for r, ev in check_duplicates(rows):
        add(r, "duplicate-pattern", "identical-same-day", ev)
    coord, patterns = check_coordinated(rows)
    for r, ev in coord:
        add(r, "coordinated", "daily-burst", ev)

    out = {"store_rows": len(rows), "already_excluded": len(already), "patterns": patterns,
           "candidates": sorted(cands.values(), key=lambda c: c["leaf_idx"])}
    json.dump(out, open(args.out, "w"), indent=1)
    by = Counter(c["reason"] for c in out["candidates"])
    print(f"{len(rows)} rows scanned; {len(out['candidates'])} candidates: {dict(by)}; {len(patterns)} burst patterns")
    print(f"written to {args.out} — review, edit, then: detect.py apply --db {args.db} {args.out} --date YYYY-MM-DD")


def apply(args):
    cands = json.load(open(args.candidates))["candidates"]
    con = sqlite3.connect(args.db)
    have = {r[0] for r in con.execute("SELECT idx FROM merkle_leaves")}
    codes = {"malformed", "implausible", "duplicate-pattern", "coordinated", "test"}
    n = 0
    with con:
        for c in cands:
            if c["leaf_idx"] not in have or c["reason"] not in codes:
                sys.exit(f"bad candidate: {c}")
            con.execute("INSERT OR IGNORE INTO exclusions (leaf_idx, reason, noted_on) VALUES (?, ?, ?)",
                        (c["leaf_idx"], c["reason"], args.date))
            n += 1
    print(f"{n} exclusions recorded with noted_on={args.date}. Delete {args.candidates} now.")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("scan")
    s.add_argument("--db", required=True)
    s.add_argument("--out", required=True)
    s.add_argument("--since", help="only rows received on or after this day")
    s.add_argument("--taxonomy", default=TAX)
    a = sub.add_parser("apply")
    a.add_argument("candidates")
    a.add_argument("--db", required=True)
    a.add_argument("--date", required=True, help="noted_on date for the exclusion list")
    args = ap.parse_args()
    scan(args) if args.cmd == "scan" else apply(args)


if __name__ == "__main__":
    main()
