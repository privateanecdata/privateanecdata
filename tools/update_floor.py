"""
The update floor (RELEASE_SPEC.md, "Tables update in batches of at least five"). One implementation:
release.py uses it to decide what each release updates, and verify_release.py --db re-runs it on the
store as it stood at that release and requires the same answer. Nothing here reads or writes files.

A *unit* is anything published as one piece and computed from one set of reports:

  compound:<id>               a compound's one-way tables (T1–T6, T10, T12 status, T16)
  compound:<id>/T12/stopped   the stop-reason row: reports on the compound that stopped
  compound:<id>/T8/<goal>     one row of outcome-by-goal: reports that chose that goal
  compound:<id>/T11/<effect>  one row of effect timing: reports that noted that effect
  class:<id>/pool             the pool: reports on the class's compounds that have no tables of their own
  class:<id>                  a class's one-way tables, built from its compounds' reports *as published*
                              plus the pool (classes publish no cross-tabulated tables)
  overall/other               the pool of "other (not listed)" reports
  overall                     the all-reports tables (T6 overall, T13, T15), built from the classes as
                              published plus that pool

Every published unit carries a record: the release that computed it, that release's date and log
length, and the number of reports. A unit's reports *as of* its record are the rows committed
before that log length and not excluded by that date — so the set a unit was computed from can be
rebuilt from the store at any later time. A unit is updated when the set it would be computed from
now differs from its as-of set by at least FLOOR reports; otherwise it is held: its record is kept
and its earlier tables are republished unchanged. Composite units (a class, all reports) record
which component records they were built from, and update when any component did.

Pools carry the rule for reports that are visible only pooled: a compound is first published only
when at least FLOOR of its reports are newer than the pool's last update (or none of its reports
were ever in the pool), so that its earlier, pooled reports cannot be separated out by subtraction;
and the pool itself updates only in batches of FLOOR.
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


class Store:
    """Rows with log positions and exclusion dates; answers "which rows were live as of (log length, date)"."""

    def __init__(self, rows, leaves, exclusions):
        self.pos = {idx: i for i, (idx, _) in enumerate(leaves)}
        self.n_leaves = len(leaves)
        self.excl = {x["leaf_idx"]: x["noted_on"] for x in exclusions}
        self.rows = rows

    def live(self, r, leaves, date):
        p = self.pos.get(r["_leaf_idx"])
        if p is None or p >= leaves:
            return False
        d = self.excl.get(r["_leaf_idx"])
        return d is None or d > date

    def asof(self, rows, spec):
        return [r for r in rows if self.live(r, spec["leaves"], spec["date"])]


def change(a, b):
    """How many reports differ between two sets of rows (added or removed)."""
    return len({r["_leaf_idx"] for r in a} ^ {r["_leaf_idx"] for r in b})


class Unit:
    def __init__(self, key):
        self.key = key
        self.rows = []            # the reports this release computes (or republishes) the unit from
        self.record = None        # the record this release carries for the unit
        self.published = False
        self.held = False
        self.why = ""


def effects_of(row):
    import json
    return [x["id"] for x in json.loads(row["adverse_effects"])]


def plan(tax, rows, leaves, exclusions, prior_units, release, date):
    """
    tax: the taxonomy dict. rows: every stored row (excluded ones included), each with "_leaf_idx".
    leaves: the log as (idx, leaf) in order. exclusions: [{leaf_idx, reason, noted_on}].
    prior_units: the prior release's "units" map, or {}. Returns {key: Unit} for every unit.
    """
    st = Store(rows, leaves, exclusions)
    now = {"leaves": st.n_leaves, "date": date}
    units = {}

    def rec(n, **extra):
        return {"release": release, "date": date, "leaves": st.n_leaves, "n": n, **extra}

    by_comp = {}
    for r in rows:
        by_comp.setdefault(r["compound"], []).append(r)
    comps = {c["id"]: c for c in tax["compounds"]}
    universal_ae = [a["id"] for a in tax["universalAdverseEffects"]]
    current = {c: st.asof(by_comp.get(c, []), now) for c in list(comps) + [OTHER]}

    # 1. Each compound's one-way tables.
    candidates = set()
    for c in comps:
        u = units[f"compound:{c}"] = Unit(f"compound:{c}")
        prev = prior_units.get(u.key)
        cur = current[c]
        if prev is None:
            if len(cur) >= UNLOCK:
                candidates.add(c)          # decided with its class's pool, below
            continue
        asof = st.asof(by_comp.get(c, []), prev)
        ch = change(asof, cur)
        if ch < FLOOR:
            u.rows, u.record, u.published, u.held = asof, prev, True, True
            u.why = f"held: {ch} changed since {prev['release']}"
        elif len(cur) >= UNLOCK:
            u.rows, u.record, u.published = cur, rec(len(cur), tier=tier_of(len(cur))), True
            u.why = f"updated: {ch} changed"
        else:
            u.why = f"no longer published: {len(cur)} reports after {ch} changes"

    # 2. Each class: its pool, first publications, and its one-way tables.
    for cls in tax["classes"]:
        members = cls["members"]
        pu = units[f"class:{cls['id']}/pool"] = Unit(f"class:{cls['id']}/pool")
        prev_p = prior_units.get(pu.key)
        cands = [m for m in members if m in candidates]

        def publish(m):
            u = units[f"compound:{m}"]
            u.rows, u.record, u.published = current[m], rec(len(current[m]), tier=tier_of(len(current[m]))), True
            u.why = "first publication"

        if prev_p is None:
            for m in cands:
                publish(m)
            unpub = [m for m in members if not units[f"compound:{m}"].published]
            pu.rows = [r for m in unpub for r in current[m]]
            pu.record = rec(len(pu.rows), members=unpub)
            pu.why = "established"
        else:
            pool_asof = st.asof([r for m in prev_p["members"] for r in by_comp.get(m, [])], prev_p)
            ok = []
            for m in cands:
                old = [r for r in pool_asof if r["compound"] == m]
                new = [r for r in current[m] if st.pos[r["_leaf_idx"]] >= prev_p["leaves"]]
                if not old or len(new) >= FLOOR:
                    ok.append(m)
                else:
                    units[f"compound:{m}"].why = f"first publication waits: only {len(new)} reports newer than the pool's last update"
            unpub = [m for m in members if not units[f"compound:{m}"].published and m not in ok]
            pool_now = [r for m in unpub for r in current[m]]
            ch = change(pool_asof, pool_now)
            if ch >= FLOOR or (ch == 0 and unpub != prev_p["members"]):
                for m in ok:
                    publish(m)
                pu.rows, pu.record = pool_now, rec(len(pool_now), members=unpub)
                pu.why = f"updated: {ch} changed"
            else:
                for m in ok:
                    units[f"compound:{m}"].why = f"first publication waits: the pool changed by only {ch}"
                pu.rows, pu.record, pu.held = pool_asof, prev_p, True
                pu.why = f"held: {ch} changed since {prev_p['release']}"
        cu = units[f"class:{cls['id']}"] = Unit(f"class:{cls['id']}")
        parts = {f"compound:{m}": {"leaves": units[f"compound:{m}"].record["leaves"], "date": units[f"compound:{m}"].record["date"]}
                 for m in members if units[f"compound:{m}"].published}
        parts[pu.key] = {"leaves": pu.record["leaves"], "date": pu.record["date"], "members": pu.record["members"]}
        union = [r for m in members if units[f"compound:{m}"].published for r in units[f"compound:{m}"].rows] + pu.rows
        prev_c = prior_units.get(cu.key)
        if len(union) < UNLOCK:
            cu.why = "fewer than 10 reports"
        elif prev_c and prev_c.get("parts") == parts:
            cu.rows, cu.record, cu.published, cu.held = union, prev_c, True, True
            cu.why = f"held: no part changed since {prev_c['release']}"
        else:
            cu.rows, cu.record, cu.published = union, rec(len(union), tier=tier_of(len(union)), parts=parts), True
            cu.why = "updated: a part changed"

    # 3. All reports: the "other" pool, then the union of published classes and that pool.
    ou = units["overall/other"] = Unit("overall/other")
    prev_o = prior_units.get(ou.key)
    if prev_o is None:
        ou.rows, ou.record, ou.why = current[OTHER], rec(len(current[OTHER])), "established"
    else:
        asof = st.asof(by_comp.get(OTHER, []), prev_o)
        ch = change(asof, current[OTHER])
        if ch >= FLOOR:
            ou.rows, ou.record, ou.why = current[OTHER], rec(len(current[OTHER])), f"updated: {ch} changed"
        else:
            ou.rows, ou.record, ou.held, ou.why = asof, prev_o, True, f"held: {ch} changed since {prev_o['release']}"
    au = units["overall"] = Unit("overall")
    parts = {f"class:{cls['id']}": {"leaves": units[f"class:{cls['id']}"].record["leaves"], "date": units[f"class:{cls['id']}"].record["date"]}
             for cls in tax["classes"] if units[f"class:{cls['id']}"].published}
    parts["overall/other"] = {"leaves": ou.record["leaves"], "date": ou.record["date"]}
    union = [r for cls in tax["classes"] if units[f"class:{cls['id']}"].published for r in units[f"class:{cls['id']}"].rows] + ou.rows
    prev_a = prior_units.get("overall")
    if len(union) < UNLOCK:
        au.why = "fewer than 10 reports"
    elif prev_a and prev_a.get("parts") == parts:
        au.rows, au.record, au.published, au.held = union, prev_a, True, True
        au.why = f"held: no part changed since {prev_a['release']}"
    else:
        au.rows, au.record, au.published = union, rec(len(union), tier=tier_of(len(union)), parts=parts), True
        au.why = "updated: a part changed"

    # 4. Each published compound's strata: one unit per row of a table split by status, goal or effect.
    for c, comp in comps.items():
        cu = units[f"compound:{c}"]
        if not cu.published:
            continue
        t = cu.record["tier"]
        strata = []
        if t >= 2:
            strata.append((f"compound:{c}/T12/stopped", lambda r: r["status"] == "stopped"))
        if t >= 3:
            for g in comp["goals"]:
                strata.append((f"compound:{c}/T8/{g}", (lambda g: lambda r: r["goal"] == g)(g)))
        if t >= 4:
            for a in universal_ae + comp["adverseEffects"]:
                strata.append((f"compound:{c}/T11/{a}", (lambda a: lambda r: a in effects_of(r))(a)))
        for key, member in strata:
            su = units[key] = Unit(key)
            s_now = [r for r in cu.rows if member(r)]
            prev = prior_units.get(key)
            if prev is None:
                if len(s_now) >= STRATUM_MIN:
                    su.rows, su.record, su.published, su.why = s_now, rec(len(s_now)), True, "first publication"
                continue
            s_asof = [r for r in st.asof(by_comp.get(c, []), prev) if member(r)]
            ch = change(s_asof, s_now)
            if ch < FLOOR:
                su.rows, su.record, su.published, su.held = s_asof, prev, True, True
                su.why = f"held: {ch} changed since {prev['release']}"
            elif len(s_now) >= STRATUM_MIN:
                su.rows, su.record, su.published, su.why = s_now, rec(len(s_now)), True, f"updated: {ch} changed"
            else:
                su.why = f"no longer published: {len(s_now)} reports"
    return units


def records(units):
    return {k: u.record for k, u in sorted(units.items()) if u.record}


def held(units):
    return sorted(k for k, u in units.items() if u.held)
