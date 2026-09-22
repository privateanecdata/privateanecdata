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
  3b. Applies the update floor (tools/update_floor.py): a table, or one row of a table split by
     goal or effect, is updated only once at least 5 of the reports it is computed from have
     changed since it was last computed; otherwise the earlier version is republished unchanged,
     marked with the release that computed it. Classes and all-reports tables are built from their
     compounds' reports as published plus a pool that follows the same rule.
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
import uniqueness  # noqa: E402
from pa_store import (attach_leaf_idx, load_exclusions, load_leaves, load_rows,  # noqa: E402
                      open_store, verify_store)

ROOT = os.path.normpath(os.path.join(HERE, ".."))
TAXONOMY = os.path.join(ROOT, "spec", "taxonomy.v1.json")
SPEC = os.path.join(ROOT, "spec", "RELEASE_SPEC.md")
UNIQ_CONFIG = os.path.join(ROOT, "spec", "schema.config.json")

# ---- RELEASE_SPEC.md constants. Change the spec (with its amendment procedure) before these.
SPEC_VERSION = "1.0"
TIER_BOUNDS = [(1000, 5), (200, 4), (100, 3), (50, 2), (10, 1)]
CELL_FLOOR = 5
STRATUM_MIN = 20
PCT_DENOM_MIN = 100
DEMOGRAPHICS_MIN = 200
UNLOCK = 10                      # below this an entity publishes nothing under its own name
PER_ENTITY_TABLES = ["T1", "T2", "T3", "T4", "T5", "T6", "T8", "T10", "T11", "T12", "T16"]
OVERALL = "overall"              # the all-reports entity: T6 overall, T13, T15
REASON_CODES = ["malformed", "implausible", "duplicate-pattern", "coordinated", "test"]
Z95 = 1.959964

OTHER = "other"
INJECTABLE = {"subcutaneous", "intramuscular", "intravenous"}


def tier_of(n):
    for bound, t in TIER_BOUNDS:
        if n >= bound:
            return t
    return 0


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
    """A compound or a class: the unit every per-entity table is computed for."""

    def __init__(self, kind, id, label, rows, tax, members):
        self.kind, self.id, self.label, self.rows = kind, id, label, rows
        self.n = len(rows)
        self.tier = tier_of(self.n)
        self.key = f"{kind}:{id}"
        # Publication state (set in main from tools/update_floor.py): `rows` are the reports the
        # unit is computed from this release (its as-of set when held); `n` is the current count.
        self.held, self.as_of, self.all_held = False, None, False
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


def stratum(rows, field, options, tier, label_key, label):
    if len(rows) < STRATUM_MIN:
        return {label_key: label, "n": None, "display": "fewer than 20 reports"}
    return {label_key: label, **one_way(rows, field, options, tier)}


def effects_of(row):
    return json.loads(row["adverse_effects"])


# ---------------------------------------------------------------- tables

def stratum_entry(su, compute, prior, hidden):
    """One row of a split table from its unit: hidden when unpublished, the prior release's row
    (marked as-of) when held, freshly computed otherwise."""
    if su is None or not su.published:
        return hidden
    if su.held:
        ent = dict(prior)
        ent["as_of"] = su.record["release"]
        return ent
    return compute(su.rows)


def build_tables(ents, tax, prior_T, units):
    """Returns {table_id: {...}}. Per-entity tables keyed by entity.key. A held unit's entries are
    copied from the prior release's tables rather than recomputed (tools/update_floor.py).
    Classes publish one-way tables only."""
    sh = tax.shared
    prior_T = prior_T or {}
    T = {k: {} for k in PER_ENTITY_TABLES}
    outcome_opts = sh["outcome"]
    stopped_ids = ["stopped"]
    not_stopped_ids = [i for i, _ in sh["status"] if i != "stopped"]
    prior_entry = lambda tid, key: prior_T.get(tid, {}).get(key)

    for e in ents:
        if e.pub_tier < 1:
            continue
        r, t = e.rows, e.pub_tier
        if e.held:
            for tid in ("T1", "T2", "T3", "T4", "T5", "T6", "T10", "T16"):
                pe = prior_entry(tid, e.key)
                if pe is not None:
                    T[tid][e.key] = pe
            status = (prior_entry("T12", e.key) or {}).get("status")
        else:
            T["T1"][e.key] = one_way(r, "route", tax.opts(e.routes), t)
            T["T2"][e.key] = one_way(r, "source_channel", sh["sourceChannel"], t)
            status = None
            if t >= 2:
                if e.kind == "compound":
                    T["T3"][e.key] = {"start_dose": one_way(r, "start_dose", e.dose_bands, t),
                                      "current_dose": one_way(r, "current_dose", e.dose_bands, t)}
                T["T4"][e.key] = one_way(r, "frequency", tax.opts(e.frequency), t)
                T["T5"][e.key] = one_way(r, "duration", sh["duration"], t)
                T["T6"][e.key] = one_way(r, "purity_tested", sh["purityTested"], t)
                # T8 later publishes the exact size of every goal stratum it shows, so T16 is the
                # single source of exact goal counts: its complement is chosen among goals T8 would
                # not show exactly anyway (under 20), and T8 shows a stratum's n only if T16 shows it.
                T["T16"][e.key] = one_way(r, "goal", tax.opts(e.goals + [OTHER]), t,
                                          prefer=lambda c: 0 if c["count"] < STRATUM_MIN else 1)
                # T10: multi-select, cell floor only — cells do not sum to n, so no complement.
                counts, none = Counter(), 0
                for row in r:
                    ids = [x["id"] for x in effects_of(row)]
                    none += not ids
                    counts.update(ids)
                cells = [{"id": "none", "label": "No side effects reported", "count": none}]
                cells += [{"id": i, "label": l, "count": counts.get(i, 0)} for i, l in tax.opts(e.aes)]
                for c in cells:
                    c["suppressed"] = c["count"] < CELL_FLOOR
                percent = t >= 4 and len(r) >= PCT_DENOM_MIN
                T["T10"][e.key] = {"n": len(r), "percent": percent, "cells": render_cells(cells, len(r), percent)}
                # T12a: status. T12b publishes the stopped subtotal, so both it and its complement
                # are published marginals of this table, and the stopped cell is never chosen as
                # the complement (hiding it would protect nothing while T12b prints the number).
                status = one_way(r, "status", sh["status"], t, groups=[stopped_ids, not_stopped_ids],
                                 prefer=lambda c: 1 if c["id"] == "stopped" else 0)
        if t < 2:
            continue
        # T12b: stop reason among the stopped — its own unit; never for a class.
        if e.kind == "class":
            stop = {"stratum": "Stopped", "n": None, "display": "not published for a class"}
        else:
            stop = stratum_entry(e.strata.get(f"{e.key}/T12/stopped"),
                                 lambda rows: {"stratum": "Stopped", **one_way(rows, "stop_reason", sh["stopReason"], t)},
                                 (prior_entry("T12", e.key) or {}).get("stop_reason"),
                                 {"stratum": "Stopped", "n": None, "display": "fewer than 20 reports"})
        T["T12"][e.key] = {"status": status, "stop_reason": stop}
        if e.kind == "class" or t < 3:
            continue
        # T8: outcome by goal, one unit per goal. "Other" is counted as a goal but is not a stratum.
        goal_shown = {c["id"] for c in T["T16"][e.key]["cells"] if c["count"] is not None}
        prior_strata = {st["goal"]: st for st in (prior_entry("T8", e.key) or {}).get("strata", [])}
        T["T8"][e.key] = {"n": len(r), "strata": []}
        for g in e.goals:
            su = e.strata.get(f"{e.key}/T8/{g}")
            if g in goal_shown:
                st = stratum_entry(su, (lambda g: lambda rows: {"goal": g, **one_way(rows, "outcome", outcome_opts, t)})(g),
                                   prior_strata.get(g), {"goal": g, "n": None, "display": "fewer than 20 reports"})
            else:
                # Hidden in T16 (below the floor, or the complement that protects one that is):
                # publishing this stratum's size would give the hidden count away by subtraction.
                st = {"goal": g, "n": None, "display": "fewer than 20 reports" if not (su and su.published)
                      else "not shown — its size would reveal a smaller group"}
            st["label"] = tax.labels.get(g, g)
            T["T8"][e.key]["strata"].append(st)
        if t < 4:
            continue
        # T11: onset and dechallenge per effect shown in T10, one unit per effect.
        shown = [c["id"] for c in T["T10"][e.key]["cells"] if c["count"] is not None and c["id"] != "none"]
        prior_eff = {x["effect"]: x for x in (prior_entry("T11", e.key) or {}).get("effects", [])}
        T["T11"][e.key] = {"n": len(r), "effects": []}
        for aid in shown:
            def compute(rows, aid=aid):
                def pick(field):
                    return lambda row: next(x[field] for x in effects_of(row) if x["id"] == aid)
                return {"effect": aid, "label": tax.labels.get(aid, aid), "n": len(rows),
                        "onset": one_way(rows, None, sh["onset"], t, value=pick("onset")),
                        "dechallenge": one_way(rows, None, sh["dechallenge"], t, value=pick("dechallenge"))}
            entry = stratum_entry(e.strata.get(f"{e.key}/T11/{aid}"), compute, prior_eff.get(aid),
                                  {"effect": aid, "label": tax.labels.get(aid, aid), "n": None, "display": "fewer than 20 reports"})
            T["T11"][e.key]["effects"].append(entry)

    # All reports: T6 overall and T13, from the overall unit (published classes plus the "other" pool).
    au = units[OVERALL]
    if not au.published:
        T["T6"][OVERALL] = {"n": None, "display": f"fewer than {UNLOCK} reports"}
        T["T13"] = {"n": None, "display": f"fewer than {DEMOGRAPHICS_MIN} reports"}
    elif au.held:
        T["T6"][OVERALL] = prior_T["T6"][OVERALL]
        T["T13"] = prior_T["T13"]
    else:
        rows_all, tt = au.rows, au.record["tier"]
        T["T6"][OVERALL] = one_way(rows_all, "purity_tested", sh["purityTested"], tt)
        if len(rows_all) >= DEMOGRAPHICS_MIN:
            declined = lambda field: (lambda r: r[field] if r[field] is not None else "declined")
            T["T13"] = {
                "n": len(rows_all),
                "age_band": one_way(rows_all, None, sh["ageBand"] + [("declined", "Preferred not to say")], 4, value=declined("age_band")),
                "sex": one_way(rows_all, None, sh["sex"] + [("declined", "Preferred not to say")], 4, value=declined("sex")),
            }
        else:
            T["T13"] = {"n": None, "display": f"fewer than {DEMOGRAPHICS_MIN} reports"}

    # T9: per goal, the T8 rows of every compound at tier >= 4 with a publishable stratum, side by
    # side — only when at least one participant is at tier 5 and there are at least two.
    # Everything in T9 is already public in T8; the table adds juxtaposition, never a comparison.
    T["T9"] = {}
    comps = [e for e in ents if e.kind == "compound" and e.pub_tier >= 4]
    goals = union_in_order(e.goals for e in comps)
    for g in goals:
        parts = []
        for e in comps:
            st = next((st for st in T["T8"].get(e.key, {}).get("strata", []) if st["goal"] == g and st["n"] is not None), None)
            if st:
                parts.append({"compound": e.id, "label": e.label, "tier": e.pub_tier, "n": st["n"], "percent": st["percent"], "cells": st["cells"]})
        if len(parts) >= 2 and any(pt["tier"] >= 5 for pt in parts):
            T["T9"][g] = {"goal": g, "label": tax.labels.get(g, g), "compounds": parts}
    return T


def build_t0(ents, tax, committed, excluded_by_reason, analyzed, other_n, prior):
    per_class, per_compound = [], []
    for e in ents:
        # `count` is always the current count; `tier` is the tier of the published tables, and
        # `tables_as_of` names the release that computed them when they are held.
        entry = {"id": e.id, "label": e.label, "tier": e.pub_tier,
                 "tables_as_of": e.as_of, "tables_n": len(e.rows) if e.held else None,
                 # at or past unlock but with no tables yet: its first publication waits for the
                 # batch rule (five reports newer than the pool's last update)
                 "tables_pending": e.kind == "compound" and e.n >= UNLOCK and e.pub_tier == 0}
        if e.kind == "class":
            entry["count"] = e.n if e.n >= CELL_FLOOR else None
            if entry["count"] is None:
                entry["display"] = "fewer than 5 reports"
            per_class.append(entry)
        else:
            entry["class"] = tax.class_of[e.id]
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
        "analyzed": analyzed,
        "received_since_prior_release": (committed - prior["counts"]["committed"]) if prior else None,
        "per_class": per_class,
        "per_compound": per_compound,
    }


def build_t15(rows, cfg):
    """Summary numbers from tools/uniqueness.py on the analysed rows. Never row-level output."""
    if len(rows) < UNLOCK:
        return {"n": None, "display": f"fewer than {UNLOCK} reports"}

    def flat(r):
        d = {k: (r[k] if r[k] is not None else "") for k in r if not k.startswith("_")}
        d["goals"] = d["goal"]          # the config's synthetic-mode field names
        d["outcomes"] = d["outcome"]
        d["adverse_effects"] = ",".join(sorted(x["id"] for x in effects_of(r)))
        return d
    rep = uniqueness.report(cfg, [flat(r) for r in rows], f"real:{len(rows)}")
    keep = ["qi_set", "qi_fields", "n", "unique_rows_pct", "rows_in_cells_lt5_pct", "rows_in_cells_lt10_pct",
            "rows_in_cells_lt20_pct", "median_cell_size"]
    return {"n": len(rows), "k_anonymity": [{k: r[k] for k in keep} for r in rep["k_anonymity"]],
            "note": "Uniqueness of rows in the private store on the published quasi-identifier sets. "
                    "This is a property of the store, which is never published; it is reported so the "
                    "de-identification argument in SCHEMA.md can be checked against real data."}


# ---------------------------------------------------------------- figures

def write_figures(T, ents, tax, out, release, prior_dir=None, overall=None):
    fig = os.path.join(out, "figures")
    written = []

    def put(path, content):
        full = os.path.join(fig, path)
        os.makedirs(os.path.dirname(full), exist_ok=True)
        with open(full, "w", encoding="utf-8") as f:
            f.write(content)
        written.append(os.path.join("figures", path))

    def carry(d):
        """A held entity's figures are the prior release's, byte for byte — they say which release
        they are as of in their own footer."""
        src = os.path.join(prior_dir, "figures", d)
        if not os.path.isdir(src):
            return
        for name in sorted(os.listdir(src)):
            if name.endswith(".svg"):
                os.makedirs(os.path.join(fig, d), exist_ok=True)
                shutil.copyfile(os.path.join(src, name), os.path.join(fig, d, name))
                written.append(os.path.join("figures", d, name))

    one_way_tables = [("T1", "Route", None), ("T2", "Source channel", None), ("T16", "What people took it for", None),
                      ("T4", "Frequency", None), ("T5", "Duration", None), ("T6", "Independent purity testing", None)]
    for e in ents:
        d = f"{e.kind}-{e.id}"
        if e.all_held:
            carry(d)
            continue
        for tid, title, _ in one_way_tables:
            tbl = T[tid].get(e.key)
            if tbl:
                put(f"{d}/{tid}.svg", svg.bar_chart(f"{e.label} — {title.lower()}", sub(tbl, e), tbl, release))
        if e.key in T["T3"]:
            for k, title in (("start_dose", "starting dose"), ("current_dose", "current or final dose")):
                tbl = T["T3"][e.key][k]
                put(f"{d}/T3-{k}.svg", svg.bar_chart(f"{e.label} — {title}", sub(tbl, e), tbl, release))
        if e.key in T["T10"]:
            tbl = T["T10"][e.key]
            put(f"{d}/T10.svg", svg.bar_chart(f"{e.label} — side effects reported", sub(tbl, e, multi=True), tbl, release))
        if e.key in T["T12"]:
            tbl = T["T12"][e.key]["status"]
            put(f"{d}/T12-status.svg", svg.bar_chart(f"{e.label} — still taking, stopped, or finished", sub(tbl, e), tbl, release))
            sr = T["T12"][e.key]["stop_reason"]
            if sr.get("n"):
                put(f"{d}/T12-stop_reason.svg", svg.bar_chart(f"{e.label} — main reason for stopping",
                    f"Of the {sr['n']} reports that stopped. " + ("Percent with 95% interval." if sr["percent"] else "Counts."), sr, release))
        if e.key in T["T8"]:
            t8 = T["T8"][e.key]
            rows = [{"label": s["label"], "n": s["n"], "display": s.get("display"), "cells": s.get("cells", []), "percent": s.get("percent")} for s in t8["strata"]]
            put(f"{d}/T8.svg", svg.grid_chart(f"{e.label} — what people hoped for, and what they reported",
                "Of the people who chose each goal as their main reason: how many reported no change, slight, moderate or large improvement.",
                [l for _, l in tax.shared["outcome"]], rows, release, f"n = {e.n}"))
        if e.key in T["T11"]:
            for entry in T["T11"][e.key]["effects"]:
                if entry["n"] is None:
                    continue
                rows = [{"label": "When it started", "n": entry["n"], "cells": entry["onset"]["cells"], "percent": entry["onset"]["percent"]}]
                put(f"{d}/T11-{entry['effect']}-onset.svg", svg.grid_chart(f"{e.label} — {entry['label'].lower()}: onset",
                    f"Among the {entry['n']} reports that noted this effect.", [l for _, l in tax.shared["onset"]], rows, release, f"n = {entry['n']}"))
                rows = [{"label": "After stopping", "n": entry["n"], "cells": entry["dechallenge"]["cells"], "percent": entry["dechallenge"]["percent"]}]
                put(f"{d}/T11-{entry['effect']}-dechallenge.svg", svg.grid_chart(f"{e.label} — {entry['label'].lower()}: after stopping",
                    f"Among the {entry['n']} reports that noted this effect.", [l for _, l in tax.shared["dechallenge"]], rows, release, f"n = {entry['n']}"))
    for g, t9 in T["T9"].items():
        rows = [{"label": p["label"], "n": p["n"], "cells": p["cells"], "percent": p["percent"]} for p in t9["compounds"]]
        put(f"_goals/T9-{g}.svg", svg.grid_chart(f"Goal: {t9['label']} — by compound, side by side",
            "Each row is one compound, stratified, never pooled. Read across a row, not down a column: this is not a ranking.",
            [l for _, l in tax.shared["outcome"]], rows, release, "stratified by compound"))
    if overall is not None and overall.held:
        carry("_overall")
        return written
    if T["T6"].get(OVERALL, {}).get("n"):
        tbl = T["T6"][OVERALL]
        put("_overall/T6.svg", svg.bar_chart("All reports — independent purity testing", sub(tbl), tbl, release))
    if T["T13"].get("n"):
        for k, title in (("age_band", "age"), ("sex", "sex")):
            tbl = T["T13"][k]
            put(f"_overall/T13-{k}.svg", svg.bar_chart(f"Who contributed — {title}", "All reports. Never crossed with any other field. " + ("Percent with 95% interval." if tbl["percent"] else "Counts."), tbl, release))
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
    ap.add_argument("--prior", help="directory of the previous release (required after the first): log chaining and the batch-update rule")
    ap.add_argument("--notes", help="JSON file: {\"integrity\": \"plain-language T14 note\"}")
    ap.add_argument("--taxonomy", default=TAXONOMY)
    ap.add_argument("--spec", default=SPEC)
    ap.add_argument("--uniqueness-config", default=UNIQ_CONFIG)
    ap.add_argument("--force", action="store_true", help="overwrite an existing output directory")
    args = ap.parse_args()

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

    # 3. What this release updates and what it republishes (tools/update_floor.py). Exclusions
    # must be dated on or before the release, and none may be backdated behind the prior release.
    if any(x["noted_on"] > args.date for x in exclusions):
        sys.exit("an exclusion is dated after the release date — not releasing")
    prior_T = {}
    if prior:
        prior_ex = {x["leaf_idx"] for x in json.load(open(os.path.join(args.prior, "exclusions.json")))["excluded"]}
        if {x["leaf_idx"] for x in exclusions if x["noted_on"] <= prior["date"]} != prior_ex:
            sys.exit("exclusions dated on or before the prior release differ from the prior release's list "
                     "(a backdated exclusion) — not releasing")
        for tid in PER_ENTITY_TABLES + ["T13", "T15"]:
            pth = os.path.join(args.prior, "tables", f"{tid}.json")
            if os.path.exists(pth):
                prior_T[tid] = json.load(open(pth))["data"]
    units = uf.plan(tax.raw, rows, leaves, exclusions, (prior or {}).get("units", {}), args.id, args.date)
    by_compound = {}
    for r in analyzed:
        by_compound.setdefault(r["compound"], []).append(r)
    ents = []
    for cid in tax.order:
        c, u = tax.compounds[cid], units[f"compound:{cid}"]
        e = Entity("compound", cid, c["label"], u.rows if u.published else [], tax, [cid])
        e.n = len(by_compound.get(cid, []))
        e.pub_tier = u.record["tier"] if u.published else 0
        e.held, e.as_of = u.held, (u.record["release"] if u.held else None)
        e.strata = {k: su for k, su in units.items() if k.startswith(e.key + "/")}
        e.all_held = u.published and u.held and all(su.held for su in e.strata.values() if su.published)
        ents.append(e)
    for cls in tax.classes:
        u = units[f"class:{cls['id']}"]
        e = Entity("class", cls["id"], cls["label"], u.rows if u.published else [], tax, cls["members"])
        e.n = sum(len(by_compound.get(m, [])) for m in cls["members"])
        e.pub_tier = u.record["tier"] if u.published else 0
        e.held, e.as_of, e.all_held = u.held, (u.record["release"] if u.held else None), (u.published and u.held)
        ents.append(e)
    other_n = len(by_compound.get(OTHER, []))
    au = units[OVERALL]
    for u in units.values():
        if u.why and not u.why.startswith("updated") and u.why not in ("established", "first publication"):
            print(f"update floor: {u.key}: {u.why}", file=sys.stderr)

    T = build_tables(ents, tax, prior_T, units)
    T["T0"] = build_t0(ents, tax, len(leaves), excluded_by_reason, len(analyzed), other_n, prior)
    period = [x for x in exclusions if not prior or x["noted_on"] > prior["date"]]
    notes = json.load(open(args.notes)) if args.notes else {}
    this_period = {k: sum(1 for x in period if x["reason"] == k) for k in REASON_CODES}
    if this_period["coordinated"] and "integrity" not in notes:
        sys.exit(f"{this_period['coordinated']} coordinated exclusions in this period: pass --notes with an "
                 f"\"integrity\" description of the pattern (RELEASE_SPEC T14)")
    T["T14"] = {"flagged_this_period": this_period,
                "flagged_total": {k: excluded_by_reason.get(k, 0) for k in REASON_CODES},
                "note": notes.get("integrity", "No coordinated-submission pattern was identified in this period.")}
    T["T15"] = prior_T["T15"] if au.held else build_t15(au.rows if au.published else [], json.load(open(args.uniqueness_config)))

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
              "T12": "Status and discontinuation", "T13": "Demographics", "T14": "Integrity log", "T15": "Uniqueness summary",
              "T16": "Primary goal"}
    for tid in sorted(T, key=lambda s: int(s[1:])):
        dump(os.path.join(out, "tables", f"{tid}.json"), {"table": tid, "title": titles[tid], "release": args.id, "data": T[tid]})
    dump(os.path.join(out, "exclusions.json"), {"release": args.id, "applies_to_all_releases_on_or_after": args.date,
                                                 "reason_codes": REASON_CODES, "excluded": exclusions})
    with open(os.path.join(out, "merkle", "leaves.txt"), "w") as f:
        for _, leaf in leaves:
            f.write(leaf.hex() + "\n")
    figures = write_figures(T, ents, tax, out, args.id, args.prior, au)

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
        "pipeline": {"tool": "tools/release.py", "sha256": sha256_file(os.path.abspath(__file__))},
        "merkle": {"root": v["root"], "leaves": len(leaves), "leaves_file": "merkle/leaves.txt",
                   "prior_root": prior["merkle"]["root"] if prior else None,
                   "prior_leaves": prior["merkle"]["leaves"] if prior else None},
        "counts": {"committed": len(leaves), "excluded": len(exclusions), "analyzed": len(analyzed)},
        "tiers": {e.key: e.pub_tier for e in ents},
        # Update floor (tools/update_floor.py): for every published unit, the release that computed
        # it, that release's date and log length, and its report count; `held` lists the units this
        # release republishes unchanged from the prior release.
        "units": uf.records(units),
        "held": uf.held(units),
        "files": dict(sorted(files.items())),
        "witness": "witness/ — signature, Rekor entry and OpenTimestamps proof are written beside this file by "
                   "tools/witness.sh. This file is the signed artifact and is never modified after signing.",
    }
    dump(os.path.join(out, "release.json"), release)
    print(f"release {args.id}: {len(leaves)} committed, {len(exclusions)} excluded, {len(analyzed)} analysed; "
          f"root {v['root'][:16]}…; {len(figures)} figures; {len(files)} files -> {out}")
    print("tiers:", ", ".join(f"{e.id}={e.pub_tier}" for e in ents if e.kind == "compound" and e.pub_tier))
    h = uf.held(units)
    if h:
        print(f"held under the update floor: {len(h)} units")


if __name__ == "__main__":
    main()
