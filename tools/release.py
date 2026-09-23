#!/usr/bin/env python3
"""
Generate a release from the submission store under spec/RELEASE_SPEC.md.

    python3 tools/release.py --db data/reports.db --id 2026-12 --date 2026-12-31 \\
        --out releases/2026-12 --prior releases/2026-11 [--notes notes.json]

Release ids are YYYY-MM while the cadence is monthly and YYYY-QN once it is quarterly. Pass
--prior for every release after the first: it is what chains the log and what the batch-update
rule is computed against.

What it does, in order:
  1. Verifies the store: every row's leaf recomputed and matched against the Merkle log. Aborts
     if anything is off. A release is never built from a store that fails its own check.
  2. Applies the exclusion list from the store's `exclusions` table (by log position).
  3. Computes each compound's and class's disclosure tier from its report count, and emits only
     the tables that tier permits, with cell suppression and complementary suppression.
  3b. Applies the update floor (tools/update_floor.py): each table, and each row of a table split
     by status, goal or side effect, takes in new reports only in a batch of at least 5 and lets
     excluded reports go only in a batch of at least 5; otherwise its earlier version is
     republished unchanged, marked with the release that computed it. The rule is replayed over
     every earlier release from the store. No table is computed for a class.
  4. Writes one JSON per table, one SVG per figure, the exclusion list, the Merkle leaf list,
     and release.json carrying the SHA-256 of every file. Output is byte-identical on re-run.
  5. Audits its own output: no published count below the cell floor, no file other than the
     enumerated artifacts.

Thresholds are constants in this file and are the ones in RELEASE_SPEC.md. They are not
arguments. Triggered by a person, reviewed by a person, then signed and witnessed by
tools/witness.sh.
"""
import argparse
import hashlib
import json
import math
import os
import re
import shutil
import sys
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import update_floor as uf  # noqa: E402
import release_svg as svg  # noqa: E402
from pa_store import (attach_leaf_idx, load_exclusions, load_leaves, load_rows,  # noqa: E402
                      open_store, verify_store)

ROOT = os.path.normpath(os.path.join(HERE, ".."))
TAXONOMY = os.path.join(ROOT, "spec", "taxonomy.v1.json")
SPEC = os.path.join(ROOT, "spec", "RELEASE_SPEC.md")

# ---- RELEASE_SPEC.md constants. Change the spec (with its amendment procedure) before these.
SPEC_VERSION = "1.0"
TIER_BOUNDS = [(1000, 5), (200, 4), (100, 3), (50, 2), (10, 1)]
CELL_FLOOR = 5
STRATUM_MIN = 20
PCT_DENOM_MIN = 100
DEMOGRAPHICS_MIN = 200
UNLOCK = 10                      # below this an entity publishes nothing under its own name
PER_ENTITY_TABLES = ["T1", "T2", "T3", "T4", "T5", "T6", "T8", "T10", "T11", "T12", "T16"]
OVERALL = "overall"              # the all-reports unit: T13 demographics
REASON_CODES = ["malformed", "implausible", "duplicate-pattern", "coordinated", "test"]
Z95 = 1.959964

OTHER = "other"
INJECTABLE = {"subcutaneous", "intramuscular", "intravenous"}


def tier_of(n):
    for bound, t in TIER_BOUNDS:
        if n >= bound:
            return t
    return 0


def iso_date(s):
    """True for a zero-padded YYYY-MM-DD date. Every date comparison in the pipeline is a string
    comparison, which is only right for this form."""
    import datetime
    try:
        return isinstance(s, str) and datetime.date.fromisoformat(s).isoformat() == s
    except ValueError:
        return False


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 16), b""):
            h.update(chunk)
    return h.hexdigest()


def wilson(k, n):
    p = k / n
    denom = 1 + Z95 * Z95 / n
    center = (p + Z95 * Z95 / (2 * n)) / denom
    half = Z95 * math.sqrt(p * (1 - p) / n + Z95 * Z95 / (4 * n * n)) / denom
    return [round(100 * max(0.0, center - half), 1), round(100 * min(1.0, center + half), 1)]


# ---------------------------------------------------------------- taxonomy helpers

class Tax:
    def __init__(self, path):
        self.raw = json.load(open(path))
        self.version = self.raw["version"]
        self.compounds = {c["id"]: c for c in self.raw["compounds"]}
        self.classes = self.raw["classes"]
        # The fixed order of SCHEMA.md: class by class, members in class order. Never by outcome.
        self.order = [m for cls in self.classes for m in cls["members"]]
        assert set(self.order) == set(self.compounds) and len(self.order) == len(self.compounds), "classes must partition compounds"
        self.class_of = {m: cls["id"] for cls in self.classes for m in cls["members"]}
        self.classes_members = {cls["id"]: list(cls["members"]) for cls in self.classes}
        self.labels = {}
        for key in ("goals", "universalAdverseEffects", "adverseEffects", "routes", "frequency"):
            for o in self.raw[key]:
                self.labels[o["id"]] = o["label"]
        self.shared = {k: [(o["id"], o["label"]) for o in v] for k, v in self.raw["shared"].items()}
        self.universal_ae = [o["id"] for o in self.raw["universalAdverseEffects"]]
        self.labels[OTHER] = "Other (not listed)"

    def opts(self, ids):
        return [(i, self.labels.get(i, i)) for i in ids]


def union_in_order(lists):
    seen, out = set(), []
    for lst in lists:
        for x in lst:
            if x not in seen:
                seen.add(x)
                out.append(x)
    return out


class Entity:
    """A compound: the unit every per-compound table is computed for. (Classes publish counts only.)"""

    def __init__(self, kind, id, label, rows, tax, members):
        self.kind, self.id, self.label, self.rows, self.tax = kind, id, label, rows, tax
        self.n = len(rows)
        self.tier = tier_of(self.n)
        self.key = f"{kind}:{id}"
        # Publication state (set in main from tools/update_floor.py): `rows` are the reports the
        # unit is computed from this release (its as-of set when held); `n` is the current count.
        self.held, self.as_of, self.stamp = False, None, None
        self.pub_tier, self.strata = self.tier, {}
        cs = [tax.compounds[m] for m in members]
        self.routes = union_in_order(c["routes"] for c in cs)
        self.goals = union_in_order(c["goals"] for c in cs)
        self.frequency = union_in_order(c["frequency"] for c in cs) + [OTHER]
        self.aes = union_in_order([tax.universal_ae] + [c["adverseEffects"] for c in cs])
        self.dose_bands = [(f"b{i}", b) for i, b in enumerate(cs[0]["doseBands"])] if kind == "compound" else []


# ---------------------------------------------------------------- suppression

def suppress(cells, groups, prefer=None):
    """
    Mark cells below the floor, then apply complementary suppression: in any group whose total is
    published, exactly one hidden cell would be recoverable by subtraction, so another cell in that
    group is hidden too. Every published marginal must be passed as a group — the whole table, and
    any subtotal another table publishes (the stopped subtotal for T12, the non-stopped remainder
    it implies). Repeats until stable. The complement is the smallest shown cell, unless `prefer`
    ranks candidates (used by T16 to hide a goal T8 would not publish exactly anyway).
    Deterministic tie-break on id.
    """
    for c in cells:
        c["suppressed"] = c["count"] < CELL_FLOOR
    by = {c["id"]: c for c in cells}
    rank = prefer or (lambda c: 0)
    changed = True
    while changed:
        changed = False
        for g in groups:
            members = [by[i] for i in g if i in by]
            hidden = [c for c in members if c["suppressed"]]
            if len(hidden) == 1:
                shown = [c for c in members if not c["suppressed"]]
                if shown:
                    min(shown, key=lambda c: (rank(c), c["count"], c["id"]))["suppressed"] = True
                    changed = True


def render_cells(cells, n, percent):
    out = []
    for c in cells:
        if c["suppressed"]:
            out.append({"id": c["id"], "label": c["label"], "count": None, "display": "not shown"})
        else:
            d = {"id": c["id"], "label": c["label"], "count": c["count"]}
            if percent:
                d["pct"] = round(100 * c["count"] / n, 1)
                d["ci95"] = wilson(c["count"], n)
            out.append(d)
    return out


def one_way(rows, field, options, tier, groups=(), value=None, prefer=None):
    """Distribution of one field over `rows`. The denominator len(rows) is published."""
    n = len(rows)
    get = value or (lambda r: r[field])
    counts = Counter(get(r) for r in rows)
    cells = [{"id": i, "label": l, "count": counts.get(i, 0)} for i, l in options]
    suppress(cells, [[c["id"] for c in cells]] + [list(g) for g in groups], prefer)
    percent = tier >= 4 and n >= PCT_DENOM_MIN
    return {"n": n, "percent": percent, "cells": render_cells(cells, n, percent)}


def effects_of(row):
    return json.loads(row["adverse_effects"])


# ---------------------------------------------------------------- tables

def goal_table(rows, e, t):
    """T16. T8 later publishes the exact size of every goal stratum it shows, so T16 is the single
    source of exact goal counts: its complement is chosen among goals T8 would not show exactly
    anyway (under 20), and T8 shows a row only if T16 shows that goal."""
    return one_way(rows, "goal", e.tax.opts(e.goals + [OTHER]), t,
                   prefer=lambda c: 0 if c["count"] < STRATUM_MIN else 1)


def effects_table(rows, e, t):
    """T10: multi-select, cell floor only — cells do not sum to n, so no complement to protect."""
    counts, none = Counter(), 0
    for row in rows:
        ids = [x["id"] for x in effects_of(row)]
        none += not ids
        counts.update(ids)
    cells = [{"id": "none", "label": "No side effects reported", "count": none}]
    cells += [{"id": i, "label": l, "count": counts.get(i, 0)} for i, l in e.tax.opts(e.aes)]
    for c in cells:
        c["suppressed"] = c["count"] < CELL_FLOOR
    percent = t >= 4 and len(rows) >= PCT_DENOM_MIN
    return {"n": len(rows), "percent": percent, "cells": render_cells(cells, len(rows), percent)}


def shown_fn(tax):
    """For tools/update_floor.py: which goals T16 and which effects T10 show for a compound's set."""
    def shown(rows):
        if not rows:
            return {"goals": set(), "effects": set()}
        cid = rows[0]["compound"]
        e = Entity("compound", cid, tax.compounds[cid]["label"], rows, tax, [cid])
        t = tier_of(len(rows))
        return {"goals": {c["id"] for c in goal_table(rows, e, t)["cells"] if c["count"] is not None},
                "effects": {c["id"] for c in effects_table(rows, e, t)["cells"] if c["count"] is not None}}
    return shown


def row_entry(su, compute, placeholder):
    """One row of a split table from its own unit: computed from the unit's reports at the tier they
    were computed at, marked `as_of` when republished from an earlier release; otherwise the
    placeholder."""
    if su is None or not su.published:
        return placeholder
    ent = compute(su.rows, su.record["tier"])
    if su.held:
        ent["as_of"] = su.record["release"]
    return ent


def build_tables(ents, tax, units):
    """Returns {table_id: {...}}. Per-compound tables keyed by entity.key. Every unit is computed
    from its own reports (tools/update_floor.py): a held unit from the same reports as before, which
    reproduces its earlier tables exactly, marked `as_of`. No table is computed for a class."""
    sh = tax.shared
    T = {k: {} for k in PER_ENTITY_TABLES}
    outcome_opts = sh["outcome"]
    stopped_ids = ["stopped"]
    not_stopped_ids = [i for i, _ in sh["status"] if i != "stopped"]

    def mark(tbl, e):
        if e.held:
            tbl["as_of"] = e.as_of
        return tbl

    for e in ents:
        if e.pub_tier < 1:
            continue
        r, t = e.rows, e.pub_tier
        T["T1"][e.key] = mark(one_way(r, "route", tax.opts(e.routes), t), e)
        T["T2"][e.key] = mark(one_way(r, "source_channel", sh["sourceChannel"], t), e)
        if t < 2:
            continue
        T["T3"][e.key] = mark({"start_dose": one_way(r, "start_dose", e.dose_bands, t),
                               "current_dose": one_way(r, "current_dose", e.dose_bands, t)}, e)
        T["T4"][e.key] = mark(one_way(r, "frequency", tax.opts(e.frequency), t), e)
        T["T5"][e.key] = mark(one_way(r, "duration", sh["duration"], t), e)
        T["T6"][e.key] = mark(one_way(r, "purity_tested", sh["purityTested"], t), e)
        T["T16"][e.key] = mark(goal_table(r, e, t), e)
        T["T10"][e.key] = mark(effects_table(r, e, t), e)
        # T12a: status. T12b publishes the stopped subtotal, so both it and its complement are
        # published marginals of this table, and the stopped cell is never chosen as the
        # complement (hiding it would protect nothing while T12b prints the number).
        status = mark(one_way(r, "status", sh["status"], t, groups=[stopped_ids, not_stopped_ids],
                              prefer=lambda c: 1 if c["id"] == "stopped" else 0), e)
        stopped_cell = next(c for c in status["cells"] if c["id"] == "stopped")
        stop = row_entry(e.strata.get(f"{e.key}/T12/stopped"),
                         lambda rows, tt: {"stratum": "Stopped", **one_way(rows, "stop_reason", sh["stopReason"], tt)},
                         {"stratum": "Stopped", "n": None,
                          "display": "fewer than 20 reports" if (stopped_cell["count"] or 0) < STRATUM_MIN else "not shown"})
        T["T12"][e.key] = {"status": status, "stop_reason": stop}
        if t < 3:
            continue
        # T8: outcome by goal, one unit per goal. "Other" is counted as a goal but is not a row. A
        # goal T16 hides (below the floor, or the complement protecting one that is) is "not shown"
        # whatever its size — one label for both, so the label itself reveals nothing; otherwise the
        # label follows the count T16 publishes.
        goal_cells = {c["id"]: c for c in T["T16"][e.key]["cells"]}
        T["T8"][e.key] = {"n": len(r), "strata": []}
        for g in e.goals:
            gc = goal_cells.get(g, {}).get("count")
            ph = {"goal": g, "n": None,
                  "display": "not shown" if gc is None or gc >= STRATUM_MIN else "fewer than 20 reports"}
            st = row_entry(e.strata.get(f"{e.key}/T8/{g}"),
                           (lambda g: lambda rows, tt: {"goal": g, **one_way(rows, "outcome", outcome_opts, tt)})(g), ph)
            st["label"] = tax.labels.get(g, g)
            T["T8"][e.key]["strata"].append(st)
        if t < 4:
            continue
        # T11: onset and dechallenge per effect shown in T10, one unit per effect.
        eff_cells = {c["id"]: c for c in T["T10"][e.key]["cells"]}
        T["T11"][e.key] = {"n": len(r), "effects": []}
        for aid in [c["id"] for c in T["T10"][e.key]["cells"] if c["count"] is not None and c["id"] != "none"]:
            def compute(rows, tt, aid=aid):
                def pick(field):
                    return lambda row: next(x[field] for x in effects_of(row) if x["id"] == aid)
                return {"effect": aid, "label": tax.labels.get(aid, aid), "n": len(rows),
                        "onset": one_way(rows, None, sh["onset"], tt, value=pick("onset")),
                        "dechallenge": one_way(rows, None, sh["dechallenge"], tt, value=pick("dechallenge"))}
            ph = {"effect": aid, "label": tax.labels.get(aid, aid), "n": None,
                  "display": "fewer than 20 reports" if eff_cells[aid]["count"] < STRATUM_MIN else "not shown"}
            T["T11"][e.key]["effects"].append(row_entry(e.strata.get(f"{e.key}/T11/{aid}"), compute, ph))

    # All reports: T13 demographics, from the all-reports unit. Never crossed with anything.
    au = units[OVERALL]
    if au.published and len(au.rows) >= DEMOGRAPHICS_MIN:
        rows_all = au.rows
        declined = lambda field: (lambda r: r[field] if r[field] is not None else "declined")
        T["T13"] = {
            "n": len(rows_all),
            "age_band": one_way(rows_all, None, sh["ageBand"] + [("declined", "Preferred not to say")], 4, value=declined("age_band")),
            "sex": one_way(rows_all, None, sh["sex"] + [("declined", "Preferred not to say")], 4, value=declined("sex")),
        }
        if au.held:
            T["T13"]["as_of"] = au.record["release"]
    else:
        T["T13"] = {"n": None, "display": f"fewer than {DEMOGRAPHICS_MIN} reports"}

    # T9: per goal, the T8 rows of every compound at tier >= 4 with a shown row, side by side — only
    # when at least one participant is at tier 5 and there are at least two. Everything in T9 is
    # already public in T8; the table adds juxtaposition, never a comparison.
    T["T9"] = {}
    comps = [e for e in ents if e.pub_tier >= 4]
    for g in union_in_order(e.goals for e in comps):
        parts = []
        for e in comps:
            st = next((st for st in T["T8"].get(e.key, {}).get("strata", []) if st["goal"] == g and st["n"] is not None), None)
            if st:
                parts.append({"compound": e.id, "label": e.label, "tier": e.pub_tier, "n": st["n"], "percent": st["percent"], "cells": st["cells"],
                              **({"as_of": st["as_of"]} if st.get("as_of") else {})})
        if len(parts) >= 2 and any(pt["tier"] >= 5 for pt in parts):
            T["T9"][g] = {"goal": g, "label": tax.labels.get(g, g), "compounds": parts}
    return T


def build_t0(ents, tax, counts, committed, excluded_by_reason, analyzed, other_n, prior):
    """Counts are current and exact. A compound's count is shown from 10; a class's from 5. For a
    compound whose tables are republished from an earlier release, the release that computed them
    and the number of reports they were computed from; `tables_pending` marks a compound whose count
    is at 10 or more while its tables wait for a batch."""
    per_class, per_compound = [], []
    for cls in tax.classes:
        n = sum(counts.get(m, 0) for m in cls["members"])
        entry = {"id": cls["id"], "label": cls["label"], "count": n if n >= CELL_FLOOR else None}
        if entry["count"] is None:
            entry["display"] = "fewer than 5 reports"
        per_class.append(entry)
    for e in ents:
        entry = {"id": e.id, "label": e.label, "class": tax.class_of[e.id], "tier": e.pub_tier,
                 "tables_as_of": e.as_of, "tables_n": len(e.rows) if e.held else None,
                 "tables_pending": e.n >= UNLOCK and e.pub_tier == 0}
        entry["count"] = e.n if e.n >= UNLOCK else None
        if entry["count"] is None:
            entry["display"] = "fewer than 10 reports — not enough to show"
        per_compound.append(entry)
    per_compound.append({"id": OTHER, "label": tax.labels[OTHER], "class": None, "tier": None,
                         "count": other_n if other_n >= 10 else None,
                         **({} if other_n >= 10 else {"display": "fewer than 10 reports — not enough to show"})})
    return {
        "committed": committed,
        "excluded": {"total": sum(excluded_by_reason.values()), "by_reason": {k: excluded_by_reason.get(k, 0) for k in REASON_CODES}},
        "not_excluded": analyzed,
        "received_since_prior_release": (committed - prior["counts"]["committed"]) if prior else None,
        "per_class": per_class,
        "per_compound": per_compound,
    }


# ---------------------------------------------------------------- figures

def write_figures(T, ents, tax, out, release, overall):
    """One SVG per table. A figure is stamped with the release of the unit it belongs to, so a
    republished unit's figure is byte-identical to the earlier one; a grid whose rows are separate
    units (T8, T9) carries this release and marks republished rows in their labels."""
    fig = os.path.join(out, "figures")
    written = []

    def put(path, content):
        full = os.path.join(fig, path)
        os.makedirs(os.path.dirname(full), exist_ok=True)
        with open(full, "w", encoding="utf-8") as f:
            f.write(content)
        written.append(os.path.join("figures", path))

    asof = lambda x: f" (as of the {x['as_of']} release)" if x.get("as_of") else ""
    one_way_tables = [("T1", "Route"), ("T2", "Source channel"), ("T16", "What people took it for"),
                      ("T4", "Frequency"), ("T5", "Duration"), ("T6", "Independent purity testing")]
    for e in ents:
        d = f"compound-{e.id}"
        for tid, title in one_way_tables:
            tbl = T[tid].get(e.key)
            if tbl:
                put(f"{d}/{tid}.svg", svg.bar_chart(f"{e.label} — {title.lower()}", sub(tbl, e), tbl, e.stamp))
        if e.key in T["T3"]:
            for k, title in (("start_dose", "starting dose"), ("current_dose", "current or final dose")):
                tbl = T["T3"][e.key][k]
                put(f"{d}/T3-{k}.svg", svg.bar_chart(f"{e.label} — {title}", sub(tbl, e), tbl, e.stamp))
        if e.key in T["T10"]:
            tbl = T["T10"][e.key]
            put(f"{d}/T10.svg", svg.bar_chart(f"{e.label} — side effects reported", sub(tbl, e, multi=True), tbl, e.stamp))
        if e.key in T["T12"]:
            tbl = T["T12"][e.key]["status"]
            put(f"{d}/T12-status.svg", svg.bar_chart(f"{e.label} — still taking, stopped, or finished", sub(tbl, e), tbl, e.stamp))
            sr = T["T12"][e.key]["stop_reason"]
            if sr.get("n"):
                put(f"{d}/T12-stop_reason.svg", svg.bar_chart(f"{e.label} — main reason for stopping",
                    f"Of the {sr['n']} reports that stopped. " + ("Percent with 95% interval." if sr["percent"] else "Counts."), sr, sr.get("as_of") or release))
        if e.key in T["T8"]:
            rows = [{"label": st["label"] + asof(st), "n": st["n"], "display": st.get("display"), "cells": st.get("cells", []), "percent": st.get("percent")}
                    for st in T["T8"][e.key]["strata"]]
            put(f"{d}/T8.svg", svg.grid_chart(f"{e.label} — what people hoped for, and what they reported",
                "Of the people who chose each goal as their main reason: how many reported no change, slight, moderate or large improvement.",
                [l for _, l in tax.shared["outcome"]], rows, release, f"n = {len(e.rows)}"))
        if e.key in T["T11"]:
            for entry in T["T11"][e.key]["effects"]:
                if entry["n"] is None:
                    continue
                st = entry.get("as_of") or release
                rows = [{"label": "When it started", "n": entry["n"], "cells": entry["onset"]["cells"], "percent": entry["onset"]["percent"]}]
                put(f"{d}/T11-{entry['effect']}-onset.svg", svg.grid_chart(f"{e.label} — {entry['label'].lower()}: onset",
                    f"Among the {entry['n']} reports that noted this effect.", [l for _, l in tax.shared["onset"]], rows, st, f"n = {entry['n']}"))
                rows = [{"label": "After stopping", "n": entry["n"], "cells": entry["dechallenge"]["cells"], "percent": entry["dechallenge"]["percent"]}]
                put(f"{d}/T11-{entry['effect']}-dechallenge.svg", svg.grid_chart(f"{e.label} — {entry['label'].lower()}: after stopping",
                    f"Among the {entry['n']} reports that noted this effect.", [l for _, l in tax.shared["dechallenge"]], rows, st, f"n = {entry['n']}"))
    for g, t9 in T["T9"].items():
        rows = [{"label": p["label"] + asof(p), "n": p["n"], "cells": p["cells"], "percent": p["percent"]} for p in t9["compounds"]]
        put(f"_goals/T9-{g}.svg", svg.grid_chart(f"Goal: {t9['label']} — by compound, side by side",
            "Each row is one compound, stratified, never pooled. Read across a row, not down a column: this is not a ranking.",
            [l for _, l in tax.shared["outcome"]], rows, release, "stratified by compound"))
    if T["T13"].get("n"):
        ostamp = overall.record["release"] if overall.held else release
        for k, title in (("age_band", "age"), ("sex", "sex")):
            tbl = T["T13"][k]
            put(f"_overall/T13-{k}.svg", svg.bar_chart(f"Who contributed — {title}", "All reports. Never crossed with any other field. " + ("Percent with 95% interval." if tbl["percent"] else "Counts."), tbl, ostamp))
    return written


def sub(tbl, e=None, multi=False):
    n = tbl["n"]
    what = "Each report can list more than one effect. " if multi else ""
    how = "Percent of reports, with 95% interval and count." if tbl["percent"] else "Counts. A cell under 5, and one neighbour that would reveal it, are “not shown”."
    scope = f"{n} reports on {e.label}. " if e else f"{n} reports. "
    return scope + what + how


# ---------------------------------------------------------------- output

def dump(path, obj):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, indent=1, ensure_ascii=False)
        f.write("\n")


ALLOWED_FILE = re.compile(r"^(tables/T\d+\.json|figures/[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+\.svg|exclusions\.json|merkle/leaves\.txt)$")


def audit(out):
    """Refuse to ship a count under the floor, a denominator under the unlock, or any file that is
    not one of the enumerated artifacts (so nothing row-shaped can ride along)."""
    problems = []
    for dirpath, _, names in os.walk(out):
        for name in names:
            rel = os.path.relpath(os.path.join(dirpath, name), out)
            if not ALLOWED_FILE.match(rel):
                problems.append(f"unexpected file {rel}")
    with open(os.path.join(out, "merkle", "leaves.txt")) as f:
        for i, line in enumerate(f):
            if not re.fullmatch(r"[0-9a-f]{64}\n", line):
                problems.append(f"leaves.txt line {i + 1} is not a 32-byte hex digest")
                break

    def walk(o, path):
        if isinstance(o, dict):
            for k, v in o.items():
                if k == "count" and isinstance(v, int) and v < CELL_FLOOR:
                    problems.append(f"{path}.{k} = {v}")
                if k == "n" and isinstance(v, int) and 0 < v < 10:
                    problems.append(f"{path}.{k} = {v}")
                walk(v, f"{path}.{k}")
        elif isinstance(o, list):
            for i, v in enumerate(o):
                walk(v, f"{path}[{i}]")

    for name in sorted(os.listdir(os.path.join(out, "tables"))):
        walk(json.load(open(os.path.join(out, "tables", name))), name)
    return problems


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--db", required=True)
    ap.add_argument("--id", required=True, help="release id: YYYY-MM while monthly, YYYY-QN once quarterly")
    ap.add_argument("--date", required=True, help="release date YYYY-MM-DD (the only timestamp in the output)")
    ap.add_argument("--out", required=True)
    ap.add_argument("--prior", help="directory of the previous release: log chaining and the batch-update rule")
    ap.add_argument("--first", action="store_true", help="this is the first release (no --prior); required so a forgotten --prior cannot skip the batch rule")
    ap.add_argument("--notes", help="JSON file: {\"integrity\": \"plain-language T14 note\"}")
    ap.add_argument("--taxonomy", default=TAXONOMY)
    ap.add_argument("--spec", default=SPEC)
    ap.add_argument("--force", action="store_true", help="overwrite an existing output directory")
    args = ap.parse_args()
    if bool(args.prior) == bool(args.first):
        sys.exit("pass exactly one of --prior <previous release> or --first")
    if not iso_date(args.date):
        sys.exit(f"--date must be YYYY-MM-DD, got {args.date!r}")

    tax = Tax(args.taxonomy)
    con = open_store(args.db)
    synthetic = bool(con.execute("SELECT name FROM sqlite_master WHERE name='_synthetic'").fetchone())
    if synthetic:
        print("NOTE: this is a synthetic store (tools/synth_store.py). Output is for testing only.", file=sys.stderr)
        if "SYNTHETIC" not in args.id:
            sys.exit("a release from a synthetic store must carry SYNTHETIC in its id so it can never be mistaken for data")
    rows, leaves, exclusions = load_rows(con), load_leaves(con), load_exclusions(con)

    # 1. Verify the store before anything is computed from it.
    v = verify_store(rows, leaves)
    if not v["ok"]:
        sys.exit(f"store verification FAILED: {json.dumps(v)} — not releasing")
    attach_leaf_idx(rows, leaves)
    unknown = [x for x in exclusions if x["reason"] not in REASON_CODES]
    if unknown:
        sys.exit(f"exclusions with unknown reason codes: {unknown}")

    # 2. Exclusions, by log position.
    excluded_idx = {x["leaf_idx"] for x in exclusions}
    analyzed = [r for r in rows if r["_leaf_idx"] not in excluded_idx]
    excluded_by_reason = Counter(x["reason"] for x in exclusions)
    prior = json.load(open(os.path.join(args.prior, "release.json"))) if args.prior else None
    if prior:
        # The log is append-only: the prior release's leaves must be a prefix of today's.
        prior_leaves = [l.strip() for l in open(os.path.join(args.prior, prior["merkle"]["leaves_file"])) if l.strip()]
        ours = [l.hex() for _, l in leaves]
        if len(prior_leaves) > len(ours) or ours[: len(prior_leaves)] != prior_leaves:
            sys.exit("prior release's leaves are not a prefix of this store's log — not releasing")

    # 3. What this release shows and what it republishes (tools/update_floor.py). Exclusions only
    # grow, are dated on or before the release, and are never backdated or re-dated: the rule is
    # replayed over every earlier release from the store, so the store's exclusions dated on or
    # before the prior release must be exactly the prior release's list, dates included.
    bad = [x for x in exclusions if not iso_date(x["noted_on"])]
    if bad:
        sys.exit(f"exclusions with a date not in YYYY-MM-DD form: {bad[:3]} — not releasing")
    if any(x["noted_on"] > args.date for x in exclusions):
        sys.exit("an exclusion is dated after the release date — not releasing")
    history = []
    if prior:
        triple = lambda x: (x["leaf_idx"], x["reason"], x["noted_on"])
        prior_ex = {triple(x) for x in json.load(open(os.path.join(args.prior, "exclusions.json")))["excluded"]}
        now_ex = {triple(x) for x in exclusions}
        if not prior_ex <= now_ex:
            sys.exit("an exclusion listed by the prior release is missing or carries a different reason or date — "
                     "exclusions only grow and never change; not releasing")
        if {p for p in now_ex if p[2] <= prior["date"]} != prior_ex:
            sys.exit("an exclusion is dated on or before the prior release but was not in its list (backdated) — not releasing")
        if args.date <= prior["date"]:
            sys.exit("this release is not dated after the prior release — not releasing")
        if sha256_file(args.taxonomy) != prior["taxonomy_sha256"]:
            sys.exit("the taxonomy differs from the prior release's. Replaying earlier releases under a different "
                     "taxonomy would change what they showed; a taxonomy change needs a specification amendment and a "
                     "defined changeover, which this pipeline does not implement — not releasing")
        history = prior.get("history", []) + [{"release": prior["release"], "date": prior["date"], "leaves": prior["merkle"]["leaves"]}]
        # The replay must reproduce the prior release exactly, or this release would rest on a
        # history that never happened (a changed rule, a changed store).
        n_prior = prior["merkle"]["leaves"]
        replay = uf.plan(tax.raw, rows, leaves[:n_prior], [x for x in exclusions if x["noted_on"] <= prior["date"]],
                         history[:-1], prior["release"], prior["date"], shown_fn(tax))
        if uf.records(replay) != prior.get("units") or uf.held(replay) != prior.get("held"):
            sys.exit("replaying the rule does not reproduce the prior release's tables — the rule, the taxonomy or the "
                     "store has changed underneath it; not releasing")
    units = uf.plan(tax.raw, rows, leaves, exclusions, history, args.id, args.date, shown_fn(tax))
    by_compound = {}
    for r in analyzed:
        by_compound.setdefault(r["compound"], []).append(r)
    counts = {c: len(rs) for c, rs in by_compound.items()}
    ents = []
    for cid in tax.order:
        c, u = tax.compounds[cid], units[f"compound:{cid}"]
        e = Entity("compound", cid, c["label"], u.rows if u.published else [], tax, [cid])
        e.n = counts.get(cid, 0)
        e.pub_tier = u.record["tier"] if u.published else 0
        e.held, e.as_of = u.held, (u.record["release"] if u.held else None)
        e.strata = {k: su for k, su in units.items() if k.startswith(e.key + "/")}
        e.stamp = u.record["release"] if u.held else args.id
        ents.append(e)
    au = units[OVERALL]
    for u in units.values():
        if u.why.startswith("held") or u.why.startswith("not shown"):
            print(f"update floor: {u.key}: {u.why}", file=sys.stderr)

    T = build_tables(ents, tax, units)
    T["T0"] = build_t0(ents, tax, counts, len(leaves), excluded_by_reason, len(analyzed), counts.get(OTHER, 0), prior)
    period = [x for x in exclusions if not prior or x["noted_on"] > prior["date"]]
    notes = json.load(open(args.notes)) if args.notes else {}
    this_period = {k: sum(1 for x in period if x["reason"] == k) for k in REASON_CODES}
    if this_period["coordinated"] and "integrity" not in notes:
        sys.exit(f"{this_period['coordinated']} coordinated exclusions in this period: pass --notes with an "
                 f"\"integrity\" description of the pattern (RELEASE_SPEC T14)")
    T["T14"] = {"flagged_this_period": this_period,
                "flagged_total": {k: excluded_by_reason.get(k, 0) for k in REASON_CODES},
                "note": notes.get("integrity", "No coordinated-submission pattern was identified in this period.")}

    # 4. Write.
    out = args.out
    if os.path.exists(out):
        if not args.force:
            sys.exit(f"{out} exists; pass --force to regenerate")
        shutil.rmtree(out)
    os.makedirs(os.path.join(out, "tables"))
    os.makedirs(os.path.join(out, "merkle"))
    titles = {"T0": "Counts", "T1": "Route", "T2": "Source channel", "T3": "Dose bands", "T4": "Frequency",
              "T5": "Duration", "T6": "Purity testing", "T8": "Outcome by goal",
              "T9": "Outcome by goal, across compounds", "T10": "Adverse effects", "T11": "Adverse effect onset and dechallenge",
              "T12": "Status and discontinuation", "T13": "Demographics", "T14": "Integrity log",
              "T16": "Primary goal"}
    for tid in sorted(T, key=lambda s: int(s[1:])):
        dump(os.path.join(out, "tables", f"{tid}.json"), {"table": tid, "title": titles[tid], "release": args.id, "data": T[tid]})
    dump(os.path.join(out, "exclusions.json"), {"release": args.id, "as_of": args.date, "reason_codes": REASON_CODES,
                                                 "note": "Each listed report leaves the tables in a batch of at least five "
                                                         "(RELEASE_SPEC.md, Cadence); the counts in T0 leave it out at once.",
                                                 "excluded": exclusions})
    with open(os.path.join(out, "merkle", "leaves.txt"), "w") as f:
        for _, leaf in leaves:
            f.write(leaf.hex() + "\n")
    figures = write_figures(T, ents, tax, out, args.id, au)

    problems = audit(out)
    if problems:
        shutil.rmtree(out)
        sys.exit("AUDIT FAILED — output removed:\n  " + "\n  ".join(problems))

    files = {}
    for dirpath, _, names in os.walk(out):
        for name in sorted(names):
            full = os.path.join(dirpath, name)
            files[os.path.relpath(full, out)] = sha256_file(full)
    release = {
        "release": args.id,
        "date": args.date,
        "synthetic": synthetic,
        "schema_version": tax.version,
        "taxonomy_sha256": sha256_file(args.taxonomy),
        "release_spec": {"version": SPEC_VERSION, "sha256": sha256_file(args.spec)},
        "pipeline": {"tool": "tools/release.py", "sha256": sha256_file(os.path.abspath(__file__)),
                     "update_floor_sha256": sha256_file(os.path.join(HERE, "update_floor.py"))},
        "merkle": {"root": v["root"], "leaves": len(leaves), "leaves_file": "merkle/leaves.txt",
                   "prior_root": prior["merkle"]["root"] if prior else None,
                   "prior_leaves": prior["merkle"]["leaves"] if prior else None},
        "counts": {"committed": len(leaves), "excluded": len(exclusions), "analyzed": len(analyzed)},
        "tiers": {e.key: e.pub_tier for e in ents},
        # Update floor (tools/update_floor.py): for every unit shown in this release, the release
        # that computed it, that release's date and the tier it was computed at — never a count, and
        # nothing for a unit that is not shown. `held` lists the shown units computed in an earlier
        # release. `history` lists every earlier release, which is what the rule is replayed over.
        "units": uf.records(units),
        "held": uf.held(units),
        "history": history,
        "files": dict(sorted(files.items())),
        "witness": "witness/ — signature, Rekor entry and OpenTimestamps proof are written beside this file by "
                   "tools/witness.sh. This file is the signed artifact and is never modified after signing.",
    }
    dump(os.path.join(out, "release.json"), release)
    print(f"release {args.id}: {len(leaves)} committed, {len(exclusions)} excluded, {len(analyzed)} not excluded; "
          f"root {v['root'][:16]}…; {len(figures)} figures; {len(files)} files -> {out}")
    print("tiers:", ", ".join(f"{e.id}={e.pub_tier}" for e in ents if e.pub_tier))
    h = uf.held(units)
    if h:
        print(f"republished unchanged under the update floor: {len(h)} units")


if __name__ == "__main__":
    main()
