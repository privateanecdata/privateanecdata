"""
Tests for the release pipeline's load-bearing pieces. No dependencies beyond the standard library.

    python3 -m unittest discover -s tools/tests -v
"""
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
TOOLS = os.path.dirname(HERE)
ROOT = os.path.dirname(TOOLS)
sys.path.insert(0, TOOLS)

import detect  # noqa: E402
import pa_store  # noqa: E402
import release  # noqa: E402


class Merkle(unittest.TestCase):
    def test_empty_root_is_hash_of_nothing(self):
        self.assertEqual(pa_store.merkle_root([]), hashlib.sha256(b"").digest())

    def test_single_leaf_is_its_own_root(self):
        leaf = hashlib.sha256(b"x").digest()
        self.assertEqual(pa_store.merkle_root([leaf]), leaf)

    def test_rfc6962_shape_with_odd_promotion(self):
        a, b, c = (hashlib.sha256(x).digest() for x in (b"a", b"b", b"c"))
        ab = hashlib.sha256(b"\x01" + a + b).digest()
        self.assertEqual(pa_store.merkle_root([a, b, c]), hashlib.sha256(b"\x01" + ab + c).digest())

    def test_order_matters(self):
        a, b = (hashlib.sha256(x).digest() for x in (b"a", b"b"))
        self.assertNotEqual(pa_store.merkle_root([a, b]), pa_store.merkle_root([b, a]))

    def test_canonical_json_matches_json_stringify(self):
        # JSON.stringify over sorted keys: no spaces, null, escaped quotes, raw non-ASCII.
        row = {"b": None, "a": 'x"y', "c": "é", "d": "[{\"id\":\"h\"}]"}
        self.assertEqual(pa_store.canonical_json(row), '{"a":"x\\"y","b":null,"c":"é","d":"[{\\"id\\":\\"h\\"}]"}')

    def test_leaf_depends_on_salt(self):
        self.assertNotEqual(pa_store.leaf_hash(b"1" * 32, "{}"), pa_store.leaf_hash(b"2" * 32, "{}"))


class Suppression(unittest.TestCase):
    def cells(self, counts):
        return [{"id": f"c{i}", "label": f"c{i}", "count": n} for i, n in enumerate(counts)]

    def hidden(self, cells):
        return [c["id"] for c in cells if c["suppressed"]]

    def test_nothing_under_floor_nothing_hidden(self):
        c = self.cells([10, 20, 5]); release.suppress(c, [[x["id"] for x in c]])
        self.assertEqual(self.hidden(c), [])

    def test_zero_is_suppressed_never_shown_as_zero(self):
        c = self.cells([30, 0, 12]); release.suppress(c, [[x["id"] for x in c]])
        self.assertIn("c1", self.hidden(c))

    def test_exactly_one_hidden_pulls_smallest_other(self):
        c = self.cells([40, 3, 9, 25]); release.suppress(c, [[x["id"] for x in c]])
        self.assertEqual(sorted(self.hidden(c)), ["c1", "c2"])

    def test_two_hidden_need_no_complement(self):
        c = self.cells([40, 3, 2, 25]); release.suppress(c, [[x["id"] for x in c]])
        self.assertEqual(sorted(self.hidden(c)), ["c1", "c2"])

    def test_two_category_table_hides_both(self):
        c = self.cells([55, 2]); release.suppress(c, [[x["id"] for x in c]])
        self.assertEqual(sorted(self.hidden(c)), ["c0", "c1"])

    def test_subgroup_total_is_protected(self):
        # status table: still 40, completed 10, stopped {3, 6, 5, 0}; the stopped subtotal is
        # published as T12b's denominator, so within the stopped group exactly-one must not occur.
        c = self.cells([40, 10, 3, 6, 5, 0])
        stopped = ["c2", "c3", "c4", "c5"]
        release.suppress(c, [[x["id"] for x in c], stopped])
        h = self.hidden(c)
        self.assertIn("c2", h); self.assertIn("c5", h)
        self.assertEqual(len([i for i in stopped if i in h]) != 1, True)
        self.assertEqual(len([i for i in [x["id"] for x in c] if i in h]) != 1, True)

    def test_subgroup_single_hidden_pulls_from_subgroup_not_elsewhere(self):
        c = self.cells([40, 10, 3, 6, 9, 12])
        stopped = ["c2", "c3", "c4", "c5"]
        release.suppress(c, [[x["id"] for x in c], stopped])
        self.assertEqual(sorted(self.hidden(c)), ["c2", "c3"])

    def test_status_table_protects_both_partitions(self):
        # The stopped subtotal is published by T12b, so n minus it is published too: neither the
        # stopped nor the not-stopped partition may end with exactly one hidden cell.
        c = self.cells([100, 3, 7, 30, 9, 40])
        stopped, not_stopped = ["c2", "c3", "c4", "c5"], ["c0", "c1"]
        release.suppress(c, [[x["id"] for x in c], stopped, not_stopped])
        h = set(self.hidden(c))
        self.assertNotEqual(len(h & set(stopped)), 1)
        self.assertNotEqual(len(h & set(not_stopped)), 1)
        self.assertIn("c1", h); self.assertIn("c0", h)

    def test_prefer_steers_the_complement(self):
        c = self.cells([3, 25, 62, 80, 12])
        release.suppress(c, [[x["id"] for x in c]], prefer=lambda x: 0 if x["count"] < 20 else 1)
        self.assertEqual(sorted(self.hidden(c)), ["c0", "c4"])   # c4 (12) preferred over c1 (25)

    def test_tie_break_is_deterministic(self):
        for _ in range(3):
            c = self.cells([7, 7, 2]); release.suppress(c, [[x["id"] for x in c]])
            self.assertEqual(sorted(self.hidden(c)), ["c0", "c2"])


class Tiers(unittest.TestCase):
    def test_boundaries(self):
        for n, t in [(0, 0), (9, 0), (10, 1), (49, 1), (50, 2), (99, 2), (100, 3), (199, 3), (200, 4), (999, 4), (1000, 5)]:
            self.assertEqual(release.tier_of(n), t, n)

    def test_percent_needs_tier_4_and_denominator_100(self):
        rows = [{"f": "a"}] * 60 + [{"f": "b"}] * 40
        self.assertFalse(release.one_way(rows[:99], "f", [("a", "A"), ("b", "B")], 4)["percent"])
        self.assertTrue(release.one_way(rows, "f", [("a", "A"), ("b", "B")], 4)["percent"])
        self.assertFalse(release.one_way(rows, "f", [("a", "A"), ("b", "B")], 3)["percent"])

    def test_wilson(self):
        lo, hi = release.wilson(50, 100)
        self.assertAlmostEqual(lo, 40.4, places=1); self.assertAlmostEqual(hi, 59.6, places=1)
        self.assertEqual(release.wilson(0, 50)[0], 0.0)
        self.assertEqual(release.wilson(50, 50)[1], 100.0)


class Detector(unittest.TestCase):
    def row(self, **kw):
        base = dict(compound="bpc-157", route="subcutaneous", goal="injury-healing", source_channel="overseas-vendor",
                    start_dose="b1", current_dose="b1", frequency="daily", duration="1-3mo",
                    purity_tested="no", status="still-taking", stop_reason=None,
                    outcome="slight", adverse_effects="[]", age_band=None, sex=None)
        base.update(kw); return base

    def test_consistent_row_is_clean(self):
        self.assertEqual(detect.check_implausible(self.row()), [])

    def test_onset_after_duration(self):
        ae = json.dumps([{"id": "headache", "onset": "after-6wk", "dechallenge": "still-taking"}])
        self.assertTrue(detect.check_implausible(self.row(duration="2-4wk", adverse_effects=ae)))

    def test_dechallenge_vs_status(self):
        ae = json.dumps([{"id": "headache", "onset": "first-days", "dechallenge": "still-taking"}])
        self.assertTrue(detect.check_implausible(self.row(status="stopped", stop_reason="cost", adverse_effects=ae)))
        self.assertEqual(detect.check_implausible(self.row(status="still-taking", adverse_effects=ae)), [])


class EndToEnd(unittest.TestCase):
    """Synthetic store -> release -> verify; then tamper and expect refusal. ~10 s."""

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp()
        cls.db = os.path.join(cls.tmp, "s.db")
        cls.py = sys.executable
        subprocess.run([cls.py, os.path.join(TOOLS, "synth_store.py"), cls.db, "--n", "1200", "--seed", "5"], check=True, capture_output=True)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp)

    def rel(self, id, out, extra=()):
        return subprocess.run([self.py, os.path.join(TOOLS, "release.py"), "--db", self.db, "--id", id, "--date", "2026-12-31",
                               "--out", out, "--force", *(extra or ["--first"])], capture_output=True, text=True)

    def test_release_verifies_and_is_deterministic(self):
        out = os.path.join(self.tmp, "r1")
        self.assertEqual(self.rel("T-SYNTHETIC", out).returncode, 0)
        h1 = {f: hashlib.sha256(open(os.path.join(out, f), "rb").read()).hexdigest() for f in json.load(open(os.path.join(out, "release.json")))["files"]}
        self.assertEqual(self.rel("T-SYNTHETIC", out).returncode, 0)
        h2 = {f: hashlib.sha256(open(os.path.join(out, f), "rb").read()).hexdigest() for f in h1}
        self.assertEqual(h1, h2)
        v = subprocess.run([self.py, os.path.join(TOOLS, "verify_release.py"), out, "--db", self.db], capture_output=True, text=True)
        self.assertEqual(v.returncode, 0, v.stdout)
        # no published count under the floor anywhere
        for name in os.listdir(os.path.join(out, "tables")):
            text = open(os.path.join(out, "tables", name)).read()
            for bad in ('"count": 1,', '"count": 2,', '"count": 3,', '"count": 4,', '"count": 0,'):
                self.assertNotIn(bad, text, name)

    def test_no_marginal_leaks_in_release(self):
        """Every published marginal has 0 or ≥2 hidden cells; T8 shows a stratum's n only if T16
        shows that goal; T12b's denominator equals the sum of stopped cells when all are shown."""
        out = os.path.join(self.tmp, "r5"); self.assertEqual(self.rel("T-SYNTHETIC", out).returncode, 0)
        T = lambda t: json.load(open(os.path.join(out, "tables", f"{t}.json")))["data"]
        t12, t16, t8 = T("T12"), T("T16"), T("T8")
        for key, tab in t12.items():
            cells = tab["status"]["cells"]
            hidden = {c["id"] for c in cells if c["count"] is None}
            stopped = {c["id"] for c in cells if c["id"] == "stopped"}
            self.assertNotEqual(len(hidden), 1, key)
            self.assertNotEqual(len(hidden & stopped), 1, key)
            self.assertNotEqual(len(hidden - stopped), 1, key)
        for key, tab in t16.items():
            hidden = [c for c in tab["cells"] if c["count"] is None]
            self.assertNotEqual(len(hidden), 1, key)
        for key, tab in t8.items():
            shown_goals = {c["id"] for c in t16[key]["cells"] if c["count"] is not None}
            for st in tab["strata"]:
                if st["n"] is not None:
                    self.assertIn(st["goal"], shown_goals, key)
                    self.assertGreaterEqual(st["n"], 20)

    def test_synthetic_store_needs_synthetic_name(self):
        self.assertNotEqual(self.rel("2026-Q4", os.path.join(self.tmp, "r2")).returncode, 0)

    def test_tampered_store_is_refused(self):
        import sqlite3
        bad = os.path.join(self.tmp, "bad.db"); shutil.copy(self.db, bad)
        con = sqlite3.connect(bad)
        # Flip one row to a value it does not already have, so the tamper is real.
        con.execute("UPDATE reports SET outcome=CASE WHEN outcome='large' THEN 'no-change' ELSE 'large' END WHERE rowid=(SELECT rowid FROM reports WHERE outcome IS NOT NULL LIMIT 1)")
        con.commit(); con.close()
        r = subprocess.run([self.py, os.path.join(TOOLS, "release.py"), "--db", bad, "--id", "X-SYNTHETIC", "--date", "2026-12-31",
                            "--out", os.path.join(self.tmp, "r3"), "--force", "--first"], capture_output=True, text=True)
        self.assertNotEqual(r.returncode, 0); self.assertIn("FAILED", r.stderr + r.stdout)

    def _tools(self, db):
        tax = os.path.join(TOOLS, "..", "spec", "taxonomy.v1.json")
        grow = lambda n, comp, seed, goal=None: subprocess.run([self.py, os.path.join(TOOLS, "synth_store.py"), db, "--n", str(n), "--seed", str(seed),
                                                                 "--append", "--day", "2026-12-20", "--compound", comp, *(["--goal", goal] if goal else [])],
                                                                check=True, capture_output=True)
        run = lambda id, out, prior=None, date="2026-12-31": subprocess.run([self.py, os.path.join(TOOLS, "release.py"), "--db", db, "--id", id, "--date", date,
                                                                             "--out", out, "--force", *(["--prior", prior] if prior else ["--first"])], capture_output=True, text=True)
        verify = lambda out, prior=None: subprocess.run([self.py, os.path.join(TOOLS, "verify_release.py"), out, *(["--prior", prior] if prior else []),
                                                          "--db", db, "--taxonomy", tax], capture_output=True, text=True)
        load = lambda out, t: json.load(open(os.path.join(out, "tables", f"{t}.json")))["data"]
        rel = lambda out: json.load(open(os.path.join(out, "release.json")))
        return tax, grow, run, verify, load, rel

    def _rehash(self, out):
        r = json.load(open(os.path.join(out, "release.json")))
        for f in r["files"]:
            r["files"][f] = hashlib.sha256(open(os.path.join(out, f), "rb").read()).hexdigest()
        json.dump(r, open(os.path.join(out, "release.json"), "w"))

    def test_update_floor_end_to_end(self):
        """Three reports on a compound: its tables are republished byte for byte and marked; T0's
        count is current. Two more: updated. The verifier replays the rule and catches tampering."""
        db = os.path.join(self.tmp, "uf.db"); shutil.copy(self.db, db)
        tax, grow, run, verify, load, rel = self._tools(db)
        hashes = lambda out: {f: hashlib.sha256(open(os.path.join(out, f), "rb").read()).hexdigest() for f in rel(out)["files"]}
        a = os.path.join(self.tmp, "ufA"); r = run("A-SYNTHETIC", a); self.assertEqual(r.returncode, 0, r.stderr)
        relA = rel(a); t0 = load(a, "T0")
        c1 = next(c for c in t0["per_compound"] if c["tier"] == 1 and c["count"] <= 40)
        k1 = f"compound:{c1['id']}"
        self.assertEqual(relA["held"], []); self.assertEqual(relA["history"], []); self.assertEqual(relA["units"][k1]["release"], "A-SYNTHETIC")
        self.assertTrue(all(k.startswith("compound:") or k == "overall" for k in relA["units"]))
        self.assertEqual([k for k in load(a, "T1") if not k.startswith("compound:")], [])       # no class tables
        self.assertNotIn("overall", load(a, "T6"))

        grow(3, c1["id"], 101)
        b = os.path.join(self.tmp, "ufB"); r = run("B-SYNTHETIC", b, a, "2027-01-31"); self.assertEqual(r.returncode, 0, r.stderr)
        relB = rel(b)
        self.assertIn(k1, relB["held"]); self.assertEqual(relB["units"][k1], relA["units"][k1])
        self.assertEqual(relB["history"], [{"release": "A-SYNTHETIC", "date": "2026-12-31", "leaves": relA["merkle"]["leaves"]}])
        strip = lambda d: {k: v for k, v in d.items() if k != "as_of"}
        for t in ("T1", "T2"):
            self.assertEqual(load(a, t)[k1], strip(load(b, t)[k1])); self.assertEqual(load(b, t)[k1]["as_of"], "A-SYNTHETIC")
        for path, h in relA["files"].items():
            if path.startswith(f"figures/compound-{c1['id']}/"):
                self.assertEqual(relB["files"][path], h, path)
        e = next(x for x in load(b, "T0")["per_compound"] if x["id"] == c1["id"])
        self.assertEqual(e["count"], c1["count"] + 3); self.assertEqual(e["tables_as_of"], "A-SYNTHETIC"); self.assertEqual(e["tables_n"], c1["count"])
        self.assertEqual(hashes(b), (run("B-SYNTHETIC", b, a, "2027-01-31"), hashes(b))[1])     # deterministic
        v = verify(b, a); self.assertEqual(v.returncode, 0, v.stdout); self.assertIn("agrees", v.stdout)
        self.assertIn("every file rebuilt from the store is identical", v.stdout)
        v = verify(b); self.assertEqual(v.returncode, 0, v.stdout)                               # replay needs no --prior

        bad = os.path.join(self.tmp, "ufB-bad"); shutil.copytree(b, bad)                         # a republished table altered
        pth = os.path.join(bad, "tables", "T1.json"); d = json.load(open(pth))
        next(c for c in d["data"][k1]["cells"] if c["count"])["count"] += 1
        json.dump(d, open(pth, "w")); self._rehash(bad)
        v = verify(bad, a); self.assertNotEqual(v.returncode, 0); self.assertIn("FAIL  updates", v.stdout)
        bad2 = os.path.join(self.tmp, "ufB-bad2"); shutil.copytree(b, bad2)                      # passed off as updated
        r2 = json.load(open(os.path.join(bad2, "release.json"))); r2["held"].remove(k1)
        for t in ("T1", "T2"):
            pth = os.path.join(bad2, "tables", f"{t}.json"); d = json.load(open(pth)); d["data"][k1].pop("as_of"); json.dump(d, open(pth, "w"))
        json.dump(r2, open(os.path.join(bad2, "release.json"), "w")); self._rehash(bad2)
        v = subprocess.run([self.py, os.path.join(TOOLS, "verify_release.py"), bad2, "--prior", a], capture_output=True, text=True)
        self.assertNotEqual(v.returncode, 0); self.assertIn("FAIL  updates", v.stdout)

        grow(2, c1["id"], 102)                                                                    # five since A
        c = os.path.join(self.tmp, "ufC"); r = run("C-SYNTHETIC", c, b, "2027-02-28"); self.assertEqual(r.returncode, 0, r.stderr)
        relC = rel(c)
        self.assertNotIn(k1, relC["held"]); self.assertEqual(relC["units"][k1], {"release": "C-SYNTHETIC", "date": "2027-02-28", "tier": 1})
        self.assertEqual(load(c, "T1")[k1]["n"], c1["count"] + 5); self.assertNotIn("as_of", load(c, "T1")[k1])
        v = verify(c, b); self.assertEqual(v.returncode, 0, v.stdout)
        grow(4, c1["id"], 103)                                                                    # the store moves on
        v = verify(c, b); self.assertEqual(v.returncode, 0, v.stdout)

    def test_prior_or_first_is_required_and_history_must_replay(self):
        db = os.path.join(self.tmp, "pf.db"); shutil.copy(self.db, db)
        tax, grow, run, verify, load, rel = self._tools(db)
        r = subprocess.run([self.py, os.path.join(TOOLS, "release.py"), "--db", db, "--id", "A-SYNTHETIC", "--date", "2026-12-31",
                            "--out", os.path.join(self.tmp, "pfX")], capture_output=True, text=True)
        self.assertNotEqual(r.returncode, 0); self.assertIn("--first", r.stderr)
        a = os.path.join(self.tmp, "pfA"); r = run("A-SYNTHETIC", a); self.assertEqual(r.returncode, 0, r.stderr)
        t2 = os.path.join(self.tmp, "tax2.json"); d = json.load(open(tax)); d["compounds"][0]["goals"] = d["compounds"][0]["goals"][:-1]
        json.dump(d, open(t2, "w"))
        r = subprocess.run([self.py, os.path.join(TOOLS, "release.py"), "--db", db, "--id", "B-SYNTHETIC", "--date", "2027-01-31",
                            "--out", os.path.join(self.tmp, "pfB"), "--prior", a, "--taxonomy", t2], capture_output=True, text=True)
        self.assertNotEqual(r.returncode, 0); self.assertIn("taxonomy differs", r.stderr)
        r = run("B-SYNTHETIC", os.path.join(self.tmp, "pfB"), a, "2026-2-28")
        self.assertNotEqual(r.returncode, 0); self.assertIn("YYYY-MM-DD", r.stderr)

    def test_exclusions_are_never_backdated_or_redated(self):
        import sqlite3
        db = os.path.join(self.tmp, "bd.db"); shutil.copy(self.db, db)
        tax, grow, run, verify, load, rel = self._tools(db)
        con = sqlite3.connect(db); con.execute("INSERT INTO exclusions (leaf_idx, reason, noted_on) VALUES (2, 'test', '2026-12-10')"); con.commit()
        a = os.path.join(self.tmp, "bdA"); r = run("A-SYNTHETIC", a); self.assertEqual(r.returncode, 0, r.stderr)
        con.execute("INSERT INTO exclusions (leaf_idx, reason, noted_on) VALUES (1, 'test', '2026-12-15')"); con.commit()
        r = run("B-SYNTHETIC", os.path.join(self.tmp, "bdB"), a, "2027-01-31")
        self.assertNotEqual(r.returncode, 0); self.assertIn("backdated", r.stderr)
        con.execute("DELETE FROM exclusions WHERE leaf_idx = 1"); con.execute("UPDATE exclusions SET noted_on = '2026-11-01' WHERE leaf_idx = 2"); con.commit()
        r = run("B-SYNTHETIC", os.path.join(self.tmp, "bdB"), a, "2027-01-31")
        self.assertNotEqual(r.returncode, 0); self.assertIn("different reason or date", r.stderr)
        con.execute("UPDATE exclusions SET noted_on = '2026-12-10', reason = 'coordinated' WHERE leaf_idx = 2"); con.commit()
        r = run("B-SYNTHETIC", os.path.join(self.tmp, "bdB"), a, "2027-01-31")
        self.assertNotEqual(r.returncode, 0); self.assertIn("different reason or date", r.stderr)
        con.execute("UPDATE exclusions SET reason = 'test' WHERE leaf_idx = 2"); con.execute("INSERT INTO exclusions (leaf_idx, reason, noted_on) VALUES (1, 'test', '2027-01-10')"); con.commit()
        b = os.path.join(self.tmp, "bdB"); r = run("B-SYNTHETIC", b, a, "2027-01-31"); self.assertEqual(r.returncode, 0, r.stderr)
        v = verify(b, a); self.assertEqual(v.returncode, 0, v.stdout)


    def test_tampered_release_fails_verification(self):
        out = os.path.join(self.tmp, "r4"); self.assertEqual(self.rel("T-SYNTHETIC", out).returncode, 0)
        p = os.path.join(out, "tables", "T1.json"); d = json.load(open(p))
        ent = next(iter(d["data"].values())); ent["cells"][0]["count"] = (ent["cells"][0]["count"] or 0) + 1
        json.dump(d, open(p, "w"))
        v = subprocess.run([self.py, os.path.join(TOOLS, "verify_release.py"), out], capture_output=True, text=True)
        self.assertNotEqual(v.returncode, 0); self.assertIn("FAIL  files", v.stdout)


class UpdateFloor(unittest.TestCase):
    """The batch rule, driven directly (tools/update_floor.py) on hand-built stores."""

    @classmethod
    def setUpClass(cls):
        import update_floor
        cls.uf = update_floor
        cls.tax = release.Tax(release.TAXONOMY)
        cls.shown = staticmethod(release.shown_fn(cls.tax))
        # a compound with at least four goals, for the T16/T8 cases
        cls.comp = next(c for c in cls.tax.raw["compounds"] if len(c["goals"]) >= 4)

    class Sim:
        def __init__(self, t):
            self.t, self.rows, self.leaves, self.excl, self.hist = t, [], [], [], []

        def add(self, k, goal=None, status="still-taking", comp=None):
            ids = []
            for _ in range(k):
                i = len(self.leaves) + 1
                self.rows.append({"_leaf_idx": i, "compound": comp or self.t.comp["id"], "goal": goal or self.t.comp["goals"][0],
                                  "status": status, "adverse_effects": "[]"})
                self.leaves.append((i, b"")); ids.append(i)
            return ids

        def exclude(self, ids, day):
            for i in ids:
                self.excl.append({"leaf_idx": i, "noted_on": day, "reason": "test"})

        def release(self, rid, day):
            units = self.t.uf.plan(self.t.tax.raw, self.rows, self.leaves, self.excl, self.hist, rid, day, self.t.shown)
            self.hist.append({"release": rid, "date": day, "leaves": len(self.leaves)})
            return units

    def key(self, suffix=""):
        return f"compound:{self.comp['id']}" + suffix

    def test_four_wait_five_enter(self):
        s = self.Sim(self); s.add(12)
        u = s.release("A", "2027-01-31")[self.key()]; self.assertTrue(u.published); self.assertEqual(len(u.rows), 12)
        s.add(4); u = s.release("B", "2027-02-28")[self.key()]; self.assertTrue(u.held); self.assertEqual(len(u.rows), 12)
        s.add(1); u = s.release("C", "2027-03-31")[self.key()]; self.assertFalse(u.held); self.assertEqual(len(u.rows), 17)

    def test_exclusions_batch_separately_by_sign(self):
        s = self.Sim(self); old = s.add(30); s.release("A", "2027-01-31")
        s.add(1); s.exclude(old[:4], "2027-02-10")                 # 1 in, 4 out: neither is a batch
        u = s.release("B", "2027-02-28")[self.key()]; self.assertTrue(u.held); self.assertEqual(len(u.rows), 30)
        s.exclude(old[4:5], "2027-03-10")                          # five out; the one new report still waits
        u = s.release("C", "2027-03-31")[self.key()]; self.assertEqual(len(u.rows), 25)
        self.assertEqual({r["_leaf_idx"] for r in u.rows}, set(old[5:]))

    def test_excluded_newcomers_never_enter_or_complete_a_batch(self):
        s = self.Sim(self); old = s.add(30); s.release("A", "2027-01-31")
        real = s.add(1); junk = s.add(4); s.exclude(junk, "2027-02-20")
        u = s.release("B", "2027-02-28")[self.key()]; self.assertTrue(u.held); self.assertEqual(len(u.rows), 30)
        s.exclude(old[:5], "2027-03-05"); s.add(5); s.exclude(s.add(4), "2027-03-20")   # five old out; 5 real + 4 junk new
        u = s.release("C", "2027-03-31")[self.key()]
        ids = {r["_leaf_idx"] for r in u.rows}
        self.assertEqual(len(u.rows), 30 - 5 + 6); self.assertFalse(ids & set(junk)); self.assertIn(real[0], ids)

    def test_withdrawn_tables_return_only_through_batches(self):
        s = self.Sim(self); old = s.add(12); s.release("A", "2027-01-31")
        s.exclude(old[:5], "2027-02-10")
        u = s.release("B", "2027-02-28")[self.key()]; self.assertFalse(u.published); self.assertIsNone(self.uf.records({"k": u}).get("k"))
        s.add(3)                                                    # count back to 10; its set is still 7
        u = s.release("C", "2027-03-31")[self.key()]; self.assertFalse(u.published)
        s.add(2)
        u = s.release("D", "2027-04-30")[self.key()]; self.assertTrue(u.published); self.assertEqual(len(u.rows), 12)

    def test_row_survives_a_tier_dip_and_returns_unchanged(self):
        g, others = self.comp["goals"][0], self.comp["goals"][1:]
        s = self.Sim(self); s.add(25, goal=g)
        per = [75 // len(others) + (1 if i < 75 % len(others) else 0) for i in range(len(others))]
        rest = [x for o, k in zip(others, per) for x in s.add(k, goal=o)]      # exactly 100 reports
        units = s.release("A", "2027-01-31"); self.assertTrue(units[self.key(f"/T8/{g}")].published)
        s.exclude(rest[:5], "2027-02-10"); n = len(s.leaves)
        units = s.release("B", "2027-02-28"); self.assertFalse(units[self.key(f"/T8/{g}")].published)
        s.add(1, goal=g); s.add(4, goal=others[0])
        units = s.release("C", "2027-03-31"); u = units[self.key(f"/T8/{g}")]
        self.assertTrue(u.published); self.assertTrue(u.held); self.assertEqual(len(u.rows), 25); self.assertEqual(u.record["release"], "A")

    def test_row_hidden_by_t16_stays_hidden_until_it_updates(self):
        g = self.comp["goals"]
        s = self.Sim(self); s.add(60, goal=g[0]); s.add(25, goal=g[1]); s.add(3, goal=g[2])
        for o in g[3:]:
            s.add(30, goal=o)
        s.add(30, goal="other")
        units = s.release("A", "2027-01-31")
        self.assertIn(g[1], set(self.comp["goals"]) - self.shown(units[self.key()].rows)["goals"])   # the complement
        self.assertFalse(units[self.key(f"/T8/{g[1]}")].published)
        s.add(5, goal=g[2])                                          # T16 now shows every goal
        units = s.release("B", "2027-02-28"); self.assertFalse(units[self.key(f"/T8/{g[1]}")].published)
        s.add(5, goal=g[1])
        units = s.release("C", "2027-03-31"); u = units[self.key(f"/T8/{g[1]}")]
        self.assertTrue(u.published); self.assertFalse(u.held); self.assertEqual(len(u.rows), 30)

    def test_tier_change_does_not_reopen_a_row_t16_hid(self):
        g = self.comp["goals"]
        s = self.Sim(self); s.add(25, goal=g[1]); s.add(3, goal=g[2])
        for o in g[3:]:
            s.add(30, goal=o)
        s.add(30, goal="other"); s.add(199 - len(s.leaves), goal=g[0])   # 199: tier 3; g[1] is the complement
        units = s.release("A", "2027-01-31")
        self.assertNotIn(g[1], self.shown(units[self.key()].rows)["goals"])
        s.add(2, goal=g[2]); s.add(2, goal=g[1]); s.add(1, goal=g[0])  # 204: tier 4; T16 opens; hair row +2 only
        units = s.release("B", "2027-02-28"); self.assertEqual(units[self.key()].record["tier"], 4)
        self.assertFalse(units[self.key(f"/T8/{g[1]}")].published)

    def test_excluded_reports_never_enter_a_row(self):
        s = self.Sim(self); s.add(30, status="stopped"); s.add(20)
        units = s.release("A", "2027-01-31"); self.assertEqual(len(units[self.key("/T12/stopped")].rows), 30)
        s.add(40)                                                     # tier 2 -> 90; no stopped
        stop_new = s.add(5, status="stopped"); s.exclude(stop_new[:1], "2027-02-20")
        units = s.release("B", "2027-02-28")
        self.assertTrue(units[self.key("/T12/stopped")].held)         # four live newcomers: not a batch
        s.add(1, status="stopped"); s.add(4)                          # a compound batch of five brings the fifth stopped report
        units = s.release("C", "2027-03-31"); ids = {r["_leaf_idx"] for r in units[self.key("/T12/stopped")].rows}
        self.assertEqual(len(ids), 35); self.assertNotIn(stop_new[0], ids)

    def test_tables_hidden_while_the_count_is_under_10(self):
        s = self.Sim(self); old = s.add(12); s.release("A", "2027-01-31")
        s.exclude(old[:3], "2027-02-10")                              # count 9; its set still 12 (3 < 5)
        u = s.release("B", "2027-02-28")[self.key()]; self.assertFalse(u.published); self.assertEqual(len(u.rows), 12)
        s.add(1)
        u = s.release("C", "2027-03-31")[self.key()]; self.assertTrue(u.published); self.assertTrue(u.held)

    def test_row_takes_percentages_when_its_compound_reaches_tier_4(self):
        g = self.comp["goals"]
        s = self.Sim(self); s.add(120, goal=g[0]); s.add(79, goal=g[1])
        units = s.release("A", "2027-01-31"); self.assertEqual(units[self.key(f"/T8/{g[0]}")].record["tier"], 3)
        s.add(5, goal=g[1])
        units = s.release("B", "2027-02-28"); u = units[self.key(f"/T8/{g[0]}")]
        self.assertFalse(u.held); self.assertEqual(u.record["tier"], 4); self.assertEqual(len(u.rows), 120)

    def test_records_name_only_shown_units_and_carry_no_counts(self):
        s = self.Sim(self); s.add(30, goal=self.comp["goals"][0]); s.add(3, comp="other")
        units = s.release("A", "2027-01-31")
        for k, r in self.uf.records(units).items():
            self.assertEqual(set(r), {"release", "date", "tier"}, k); self.assertTrue(units[k].published)



if __name__ == "__main__":
    unittest.main()
