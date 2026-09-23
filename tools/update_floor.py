"""
The update floor (RELEASE_SPEC.md, "Tables update in batches of at least five"). One implementation:
release.py uses it to decide what each release shows, and verify_release.py --db re-runs it and
requires the same answer. Nothing here reads or writes files.

A *unit* is anything published as one piece and computed from one set of reports:

  compound:<id>               a compound's one-way tables (T1–T6, T10, T12 status, T16)
  compound:<id>/T12/stopped   the stop-reason row: that compound's reports that stopped
  compound:<id>/T8/<goal>     one row of outcome-by-goal: its reports that chose that goal
  compound:<id>/T11/<effect>  one row of effect timing: its reports that noted that effect
  overall                     the all-reports table (T13: age band and sex)

Classes publish no tables (their counts are in T0). Two kinds of unit contain other units' reports:
a row, inside its own compound, and the all-reports table, which contains every report. A row's
field (outcome, onset, stop reason) appears in no other table, and the all-reports table publishes
only fields no compound table carries (age band, sex). That is what makes the rule below
sufficient: nothing can be subtracted except one version of a unit from another version of the
same unit.

Each unit has an explicit set of reports — the reports its tables are computed from. From one
release to the next the set changes only like this:

  * new reports enter only in a batch of at least FLOOR: every report that belongs to the unit, is
    committed, is not excluded as of this release, and is not yet in the set;
  * excluded reports leave only in a batch of at least FLOOR: every report in the set that is
    excluded as of this release;
  * the two batches are decided separately (in a difference between two releases they would
    separate by sign), and a report excluded before it entered a table never enters one.

A row (a stratum) takes its candidates from its compound's set, not from the store, so it can
never run ahead of its compound's tables — and only those not excluded, so an excluded report
never enters a row either. A compound's tables are shown only while both its set and its current
count are at least UNLOCK. A unit, once it exists, is never forgotten: a compound
that falls below UNLOCK, or a row below STRATUM_MIN or below the tier its table needs, is simply
not shown, and its set keeps moving by the same batches, so returning is an update, never a fresh
start.

The sets are never stored. Each release replays the rule over every earlier release (their dates
and log lengths are listed in release.json), from the store as it stood at each: rows committed
before that release's log length, exclusions noted on or before its date. Exclusions are never
backdated (release.py refuses), so the replay reproduces each earlier release exactly.

`shown(compound_rows)` is supplied by the caller: which goals T16 and which effects T10 show for a
compound's current set. A row of T8 or T11 is shown only if its table's parent cell is shown now
and was shown when the row's set was last computed, so a row republished from an earlier release
never reveals a count that release's suppression hid. When a shown row's compound changes tier
(and so gains or loses percentages) the row is re-stamped with the same set and the same flag.
"""

FLOOR = 5
UNLOCK = 10
STRATUM_MIN = 20
TIER_BOUNDS = [(1000, 5), (200, 4), (100, 3), (50, 2), (10, 1)]
OTHER = "other"


def tier_of(n):
    for bound, t in TIER_BOUNDS:
        if n >= bound:
            return t
    return 0


def effects_of(row):
    import json
    return [x["id"] for x in json.loads(row["adverse_effects"])]


def strata_of(comp, universal_ae):
    """Every row unit a compound can have: (suffix, tier its table needs, membership test, gate)."""
    out = [("T12/stopped", 2, lambda r: r["status"] == "stopped", None)]
    out += [(f"T8/{g}", 3, (lambda g: lambda r: r["goal"] == g)(g), ("goals", g)) for g in comp["goals"]]
    out += [(f"T11/{a}", 4, (lambda a: lambda r: a in effects_of(r))(a), ("effects", a))
            for a in universal_ae + comp["adverseEffects"]]
    return out


class Unit:
    def __init__(self, key):
        self.key = key
        self.rows = []            # the reports its tables are computed from this release
        self.record = None        # {"release", "date", "tier"} — the release that computed the set
        self.published = False    # shown in this release
        self.held = False         # shown, and computed in an earlier release
        self.why = ""


def _batch(S, candidates_in, candidates_out):
    """Apply the two batches to a set of leaf indices. Returns (new set, n in, n out, changed)."""
    new = S
    if len(candidates_out) >= FLOOR:
        new = new - candidates_out
    if len(candidates_in) >= FLOOR:
        new = new | candidates_in
    return new, len(candidates_in), len(candidates_out), new != S


def step(state, tax, by_comp, by_idx, live, excluded, release, date, shown):
    """One release. state: {key: {"set": frozenset, "release", "date", "tier", "shown"?}} from the
    previous release (not modified). live(idx): committed and not excluded as of this release.
    excluded(idx): excluded as of this release. Returns (new_state, units)."""
    new_state, units = dict(state), {}
    comps = {c["id"]: c for c in tax["compounds"]}
    universal_ae = [a["id"] for a in tax["universalAdverseEffects"]]
    rec = lambda n, **kw: {"release": release, "date": date, "tier": tier_of(n), **kw}

    def settle(key, cand_in, cand_out, first, need, current):
        """Common path for compounds and the all-reports unit. Shown only while both the set and the
        current count are at least `need`."""
        u = units[key] = Unit(key)
        st = state.get(key)
        if st is None:
            if len(first) < need:
                return u, None
            S, st2 = frozenset(first), None
            new_state[key] = st2 = {"set": S, **rec(len(S))}
            u.why = "first publication"
        else:
            S, n_in, n_out, changed = _batch(st["set"], cand_in(st["set"]), cand_out(st["set"]))
            st2 = {"set": S, **rec(len(S))} if changed else st
            new_state[key] = st2
            u.why = (f"updated: +{n_in if n_in >= FLOOR else 0} new, -{n_out if n_out >= FLOOR else 0} excluded" if changed
                     else f"held: {n_in} new and {n_out} excluded waiting since {st['release']}")
        u.rows = [by_idx[i] for i in sorted(S)]
        u.record = {k: st2[k] for k in ("release", "date", "tier")}
        u.published = len(S) >= need and len(current) >= need
        u.held = u.published and st2["release"] != release
        if not u.published:
            u.why = f"not shown: {len(S)} reports in its tables"
        return u, st2

    # 1. Compounds.
    for c in comps:
        ids_live = {r["_leaf_idx"] for r in by_comp.get(c, []) if live(r["_leaf_idx"])}
        settle(f"compound:{c}",
               lambda S, ids_live=ids_live: frozenset(ids_live - S),
               lambda S: frozenset(i for i in S if excluded(i)),
               ids_live, UNLOCK, ids_live)

    # 2. Rows of each compound that has ever had tables. Candidates come from the compound's set.
    for c, comp in comps.items():
        cst = new_state.get(f"compound:{c}")
        if cst is None:
            continue
        cu = units[f"compound:{c}"]
        Sc = cst["set"]
        ctier = cst["tier"] if cu.published else 0
        gates = shown([by_idx[i] for i in sorted(Sc)]) if cu.published else {"goals": set(), "effects": set()}
        for suffix, need_tier, member, gate in strata_of(comp, universal_ae):
            key = f"compound:{c}/{suffix}"
            cand = frozenset(i for i in Sc if member(by_idx[i]) and not excluded(i))
            open_now = gate is None or gate[1] in gates[gate[0]]
            st = state.get(key)
            u = units[key] = Unit(key)
            if st is None:
                if ctier < need_tier or len(cand) < STRATUM_MIN:
                    del units[key]
                    continue
                st2 = {"set": cand, "release": release, "date": date, "tier": ctier, "shown": open_now}
                u.why = "first publication"
            else:
                T, n_in, n_out, changed = _batch(st["set"], cand - st["set"], st["set"] - Sc)
                if changed:
                    st2 = {"set": T, "release": release, "date": date, "tier": ctier or st["tier"], "shown": open_now}
                    u.why = "updated"
                elif st["shown"] and ctier >= need_tier and ctier != st["tier"]:
                    # A shown row takes the percentages its compound's tier grants when that tier
                    # changes: same set, same flag, re-stamped — nothing new about its reports.
                    st2 = {**st, "release": release, "date": date, "tier": ctier}
                    u.why = "updated: tier changed"
                else:
                    st2 = st
                    u.why = f"held: {n_in} new and {n_out} out waiting since {st['release']}"
            new_state[key] = st2
            u.rows = [by_idx[i] for i in sorted(st2["set"])]
            u.record = {k: st2[k] for k in ("release", "date", "tier")}
            u.published = (ctier >= need_tier and len(st2["set"]) >= STRATUM_MIN and open_now and st2["shown"])
            u.held = u.published and st2["release"] != release
            if not u.published:
                u.why = "not shown"

    # 3. All reports.
    all_live = {i for i, r in by_idx.items() if live(i)}
    settle("overall",
           lambda S: frozenset(all_live - S),
           lambda S: frozenset(i for i in S if excluded(i)),
           all_live, UNLOCK, all_live)
    return new_state, units


def plan(tax, rows, leaves, exclusions, history, release, date, shown):
    """
    Replay the rule over every earlier release, then decide this one.

    tax: the taxonomy dict. rows: every stored row with "_leaf_idx" (from pa_store.attach_leaf_idx).
    leaves: the log, (idx, leaf) in order — at least as long as this release. exclusions: every
    exclusion in the store. history: [{"release", "date", "leaves"}] of earlier releases, oldest
    first. `release`/`date`: this release; its log length is len(leaves). Returns {key: Unit}.
    """
    pos = {idx: i for i, (idx, _) in enumerate(leaves)}
    noted = {x["leaf_idx"]: x["noted_on"] for x in exclusions}
    by_idx = {r["_leaf_idx"]: r for r in rows if r.get("_leaf_idx") is not None}
    by_comp = {}
    for r in by_idx.values():
        by_comp.setdefault(r["compound"], []).append(r)
    state, units = {}, {}
    for h in list(history) + [{"release": release, "date": date, "leaves": len(leaves)}]:
        L, D = h["leaves"], h["date"]
        committed = {i: r for i, r in by_idx.items() if pos.get(i, L) < L}
        excluded = lambda i, D=D: i in noted and noted[i] <= D
        live = lambda i, committed=committed, excluded=excluded: i in committed and not excluded(i)
        view_by_comp = {c: [r for r in rs if r["_leaf_idx"] in committed] for c, rs in by_comp.items()}
        state, units = step(state, tax, view_by_comp, by_idx, live, excluded, h["release"], h["date"], shown)
    return units


def records(units):
    """What release.json publishes: for every unit shown in this release, the release that computed
    it, that release's date, and the tier its tables were computed at. Never a count, and nothing
    for a unit that is not shown (its existence would say something about its size)."""
    return {k: u.record for k, u in sorted(units.items()) if u.published}


def held(units):
    return sorted(k for k, u in units.items() if u.held)
