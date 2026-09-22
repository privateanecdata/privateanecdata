#!/usr/bin/env python3
"""
Uniqueness / k-anonymity analysis for the submission schema.

This is the gate that decides whether the schema is finished. It answers: on the coarsened
row the server actually receives, how many contributors are unique on the attributes an
outside adversary could plausibly know?

Two modes:

  synthetic   Generate rows from a schema config with stated skew assumptions and analyze.
              Run before launch at n = 500 / 5,000 / 50,000. Publish the output.

  real        Analyze a CSV of actual rows (operator-private). Run before every release.
              Never publish row-level output; publish only the summary numbers.

Quasi-identifier (QI) sets are defined in the config. "narrow" is what someone could know
from a public post ("35M, started BPC-157 250mcg/day in March for a tendon"). "broad" adds
everything else. Both are reported; the narrow set is the one that matters for linkage.

Usage:
  python3 tools/uniqueness.py synthetic spec/schema.config.json --n 500 5000 50000
  python3 tools/uniqueness.py real path/to/rows.csv spec/schema.config.json
"""

import argparse
import csv
import json
import math
import random
import sys
from collections import Counter, defaultdict


# ---------------------------------------------------------------- distributions

def zipf_weights(n, s=1.0):
    """Zipf weights for n categories with exponent s. s=0 is uniform."""
    w = [1.0 / ((i + 1) ** s) for i in range(n)]
    t = sum(w)
    return [x / t for x in w]


def middle_heavy(n):
    """Weights that put most mass in the middle bands (for dose buckets)."""
    if n == 1:
        return [1.0]
    mid = (n - 1) / 2.0
    w = [math.exp(-((i - mid) ** 2) / (2 * (n / 3.5) ** 2)) for i in range(n)]
    t = sum(w)
    return [x / t for x in w]


def recent_heavy(n):
    """Weights favoring the most recent buckets (for quarter-started)."""
    w = [math.exp(-0.45 * (n - 1 - i)) for i in range(n)]
    t = sum(w)
    return [x / t for x in w]


def resolve_weights(field, k):
    """Pick a weight vector for a field with k options based on its declared skew."""
    skew = field.get("skew", "uniform")
    if isinstance(skew, list):
        if len(skew) != k:
            raise ValueError(f"field {field['id']}: explicit weights length {len(skew)} != {k} options")
        t = sum(skew)
        return [x / t for x in skew]
    if skew == "uniform":
        return [1.0 / k] * k
    if skew == "zipf":
        return zipf_weights(k, field.get("zipf_s", 1.0))
    if skew == "zipf-mild":
        return zipf_weights(k, 0.6)
    if skew == "middle":
        return middle_heavy(k)
    if skew == "recent":
        return recent_heavy(k)
    raise ValueError(f"unknown skew {skew!r} on field {field['id']}")


def choose(rng, options, weights):
    return rng.choices(options, weights=weights, k=1)[0]


# ---------------------------------------------------------------- synthetic rows

def generate_rows(cfg, n, seed=20260910):
    """
    Generate n synthetic rows. Compound is drawn first; compound-dependent fields
    (goals, dose bands, adverse effects) are drawn from that compound's own vocabulary.
    """
    rng = random.Random(seed)
    compounds = cfg["compounds"]
    comp_ids = [c["id"] for c in compounds]
    comp_w = resolve_weights({"id": "compound", "skew": cfg.get("compound_skew", "zipf"),
                              "zipf_s": cfg.get("compound_zipf_s", 1.1)}, len(comp_ids))
    by_id = {c["id"]: c for c in compounds}

    shared = cfg["shared_fields"]
    rows = []
    for _ in range(n):
        row = {}
        cid = choose(rng, comp_ids, comp_w)
        comp = by_id[cid]
        row["compound"] = cid

        # compound-dependent single-select fields
        for fname in ("start_dose", "current_dose"):
            bands = comp["dose_bands"]
            row[fname] = choose(rng, bands, middle_heavy(len(bands)))

        # goals: multi-select, typically 1-2 chosen, first-listed goals more common
        goals = comp["goals"]
        gw = zipf_weights(len(goals), 0.8)
        max_goals = cfg.get("max_goals", 3)
        n_goals = choose(rng, [1, 2, 3], [0.55, 0.35, 0.10]) if max_goals >= 3 else (choose(rng, [1, 2], [0.6, 0.4]) if max_goals == 2 else 1)
        chosen = set()
        while len(chosen) < min(n_goals, len(goals)):
            chosen.add(choose(rng, goals, gw))
        row["goals"] = "|".join(sorted(chosen))

        # per-goal outcome on the shared scale
        scale = shared["outcome_scale"]["options"]
        sw = resolve_weights(shared["outcome_scale"], len(scale))
        row["outcomes"] = "|".join(f"{g}={choose(rng, scale, sw)}" for g in sorted(chosen))

        # adverse effects: multi-select, most people report 0-2
        aes = comp["adverse_effects"] + shared["universal_adverse_effects"]["options"]
        aw = zipf_weights(len(aes), 0.9)
        n_ae = choose(rng, [0, 1, 2, 3], [0.40, 0.35, 0.18, 0.07])
        chosen_ae = set()
        while len(chosen_ae) < min(n_ae, len(aes)):
            chosen_ae.add(choose(rng, aes, aw))
        row["adverse_effects"] = "|".join(sorted(chosen_ae))

        # shared single-select fields
        for fid, field in shared.items():
            if fid in ("outcome_scale", "universal_adverse_effects"):
                continue
            opts = field["options"]
            row[fid] = choose(rng, opts, resolve_weights(field, len(opts)))

        rows.append(row)
    return rows


# ---------------------------------------------------------------- analysis

def analyze(rows, qi_fields, label):
    """k-anonymity summary over the given QI field list."""
    key = lambda r: tuple(r.get(f, "") for f in qi_fields)
    cells = Counter(key(r) for r in rows)
    n = len(rows)
    sizes = list(cells.values())
    per_row_cell = [cells[key(r)] for r in rows]

    def frac_rows_in_cells_leq(k):
        return sum(1 for s in per_row_cell if s <= k) / n

    sorted_sizes = sorted(per_row_cell)
    median_cell = sorted_sizes[n // 2]
    return {
        "qi_set": label,
        "qi_fields": qi_fields,
        "n": n,
        "distinct_cells": len(cells),
        "unique_rows_pct": round(100 * frac_rows_in_cells_leq(1), 1),
        "rows_in_cells_lt5_pct": round(100 * frac_rows_in_cells_leq(4), 1),
        "rows_in_cells_lt10_pct": round(100 * frac_rows_in_cells_leq(9), 1),
        "rows_in_cells_lt20_pct": round(100 * frac_rows_in_cells_leq(19), 1),
        "median_cell_size": median_cell,
        "largest_cell": max(sizes),
    }


def field_entropy(rows, field):
    c = Counter(r.get(field, "") for r in rows)
    n = len(rows)
    return -sum((v / n) * math.log2(v / n) for v in c.values() if v)


def marginal_contribution(rows, qi_fields):
    """
    For each QI field, how much does dropping it reduce uniqueness?
    This tells the schema author which field is doing the most damage.
    """
    base = analyze(rows, qi_fields, "base")["unique_rows_pct"]
    out = []
    for f in qi_fields:
        without = [x for x in qi_fields if x != f]
        u = analyze(rows, without, f"without {f}")["unique_rows_pct"]
        out.append({
            "field": f,
            "entropy_bits": round(field_entropy(rows, f), 2),
            "unique_pct_if_dropped": u,
            "reduction_pts": round(base - u, 1),
        })
    out.sort(key=lambda d: -d["reduction_pts"])
    return out


# ---------------------------------------------------------------- IO

def load_real_rows(path):
    with open(path, newline="") as f:
        return list(csv.DictReader(f))


def load_store_rows(db_path):
    """Rows straight from the submission store, flattened onto the config's field names."""
    import os
    import sys
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import pa_store
    out = []
    for r in pa_store.load_rows(pa_store.open_store(db_path)):
        d = {k: (r[k] if r[k] is not None else "") for k in pa_store.ROW_FIELDS}
        d["goals"], d["outcomes"] = d["goal"], d["outcome"]
        d["adverse_effects"] = ",".join(sorted(x["id"] for x in json.loads(r["adverse_effects"])))
        out.append(d)
    return out


def report(cfg, rows, n_label):
    results = []
    for qi_name, qi_fields in cfg["qi_sets"].items():
        results.append(analyze(rows, qi_fields, qi_name))
    narrow = cfg["qi_sets"].get("narrow") or next(iter(cfg["qi_sets"].values()))
    contrib = marginal_contribution(rows, narrow)
    return {"n": n_label, "k_anonymity": results, "marginal_contribution_narrow_qi": contrib}


def print_report(rep):
    print(f"\n=== n = {rep['n']} ===")
    for r in rep["k_anonymity"]:
        print(f"  [{r['qi_set']}] fields={len(r['qi_fields'])}  cells={r['distinct_cells']}")
        print(f"     unique rows: {r['unique_rows_pct']}%   in cells <5: {r['rows_in_cells_lt5_pct']}%"
              f"   <10: {r['rows_in_cells_lt10_pct']}%   <20: {r['rows_in_cells_lt20_pct']}%"
              f"   median cell: {r['median_cell_size']}")
    print("  marginal contribution (narrow QI) — drop this field to reduce uniqueness by:")
    for c in rep["marginal_contribution_narrow_qi"]:
        print(f"     {c['field']:<22} {c['entropy_bits']:>5} bits   -> {c['unique_pct_if_dropped']}% unique  (−{c['reduction_pts']} pts)")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="mode", required=True)
    s = sub.add_parser("synthetic")
    s.add_argument("config")
    s.add_argument("--n", type=int, nargs="+", default=[500, 5000, 50000])
    s.add_argument("--seed", type=int, default=20260910)
    s.add_argument("--json", help="write full report JSON here")
    r = sub.add_parser("real")
    r.add_argument("csv")
    r.add_argument("config")
    r.add_argument("--json")
    d = sub.add_parser("real-db", help="analyse the SQLite store directly; no row-level file is ever written")
    d.add_argument("db")
    d.add_argument("config")
    d.add_argument("--json")
    args = ap.parse_args()

    with open(args.config) as f:
        cfg = json.load(f)

    reports = []
    if args.mode == "synthetic":
        for n in args.n:
            rows = generate_rows(cfg, n, seed=args.seed)
            rep = report(cfg, rows, n)
            reports.append(rep)
            print_report(rep)
    else:
        rows = load_real_rows(args.csv) if args.mode == "real" else load_store_rows(args.db)
        rep = report(cfg, rows, f"real:{len(rows)}")
        reports.append(rep)
        print_report(rep)
        print("\n  (real mode: publish only the summary numbers above, never row-level output)")

    if args.json:
        with open(args.json, "w") as f:
            json.dump({"config": args.config, "reports": reports}, f, indent=1)
        print(f"\nwrote {args.json}")


if __name__ == "__main__":
    main()
