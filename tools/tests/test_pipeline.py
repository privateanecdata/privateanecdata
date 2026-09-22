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

    def test_stratum_under_20_is_not_published(self):
        rows = [{"f": "a"}] * 19
        s = release.stratum(rows, "f", [("a", "A")], 3, "goal", "g")
        self.assertIsNone(s["n"]); self.assertNotIn("cells", s)

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
                               "--out", out, "--force", *extra], capture_output=True, text=True)

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
                            "--out", os.path.join(self.tmp, "r3"), "--force"], capture_output=True, text=True)
        self.assertNotEqual(r.returncode, 0); self.assertIn("FAILED", r.stderr + r.stdout)

    def _tools(self, db):
        tax = os.path.join(TOOLS, "..", "spec", "taxonomy.v1.json")
        grow = lambda n, comp, seed, goal=None: subprocess.run([self.py, os.path.join(TOOLS, "synth_store.py"), db, "--n", str(n), "--seed", str(seed),
                                                                 "--append", "--day", "2026-12-20", "--compound", comp, *(["--goal", goal] if goal else [])],
                                                                check=True, capture_output=True)
        run = lambda id, out, prior=None, date="2026-12-31": subprocess.run([self.py, os.path.join(TOOLS, "release.py"), "--db", db, "--id", id, "--date", date,
                                                                             "--out", out, "--force", *(["--prior", prior] if prior else [])], capture_output=True, text=True)
        verify = lambda out, prior: subprocess.run([self.py, os.path.join(TOOLS, "verify_release.py"), out, "--prior", prior, "--db", db, "--taxonomy", tax],
                                                   capture_output=True, text=True)
        load = lambda out, t: json.load(open(os.path.join(out, "tables", f"{t}.json")))["data"]
        rel = lambda out: json.load(open(os.path.join(out, "release.json")))
        return tax, grow, run, verify, load, rel

    def test_update_floor_holds_small_changes_and_updates_at_five(self):
        """A table is updated only after at least five of its reports changed; until then it is
        republished byte for byte and marked as-of. Classes and all-reports follow their parts."""
        db = os.path.join(self.tmp, "uf.db"); shutil.copy(self.db, db)
        tax, grow, run, verify, load, rel = self._tools(db)
        hashes = lambda out: {f: hashlib.sha256(open(os.path.join(out, f), "rb").read()).hexdigest() for f in rel(out)["files"]}
        a = os.path.join(self.tmp, "ufA"); r = run("A-SYNTHETIC", a); self.assertEqual(r.returncode, 0, r.stderr)
        relA = rel(a); t0 = load(a, "T0")
        c1 = next(c for c in t0["per_compound"] if c["tier"] == 1 and c["count"] <= 40)
        k1, kc = f"compound:{c1['id']}", f"class:{c1['class']}"
        self.assertEqual(relA["held"], []); self.assertEqual(relA["units"][k1]["release"], "A-SYNTHETIC")

        grow(3, c1["id"], 101)                                   # under the floor
        b = os.path.join(self.tmp, "ufB"); r = run("B-SYNTHETIC", b, a, "2027-01-31"); self.assertEqual(r.returncode, 0, r.stderr)
        relB = rel(b)
        self.assertIn(k1, relB["held"]); self.assertEqual(relB["units"][k1], relA["units"][k1])
        for t in ("T1", "T2"):
            self.assertEqual(load(a, t)[k1], load(b, t)[k1])
        for path, h in relA["files"].items():
            if path.startswith(f"figures/compound-{c1['id']}/"):
                self.assertEqual(relB["files"][path], h, path)
        e = next(x for x in load(b, "T0")["per_compound"] if x["id"] == c1["id"])
        self.assertEqual(e["count"], c1["count"] + 3); self.assertEqual(e["tables_as_of"], "A-SYNTHETIC"); self.assertEqual(e["tables_n"], c1["count"])
        self.assertIn(kc, relB["held"]); self.assertIn("overall", relB["held"])   # no part changed
        self.assertEqual(hashes(b), (run("B-SYNTHETIC", b, a, "2027-01-31"), hashes(b))[1])
        v = verify(b, a); self.assertEqual(v.returncode, 0, v.stdout)
        self.assertIn("ok    updates", v.stdout); self.assertIn("agrees", v.stdout)
        bad = os.path.join(self.tmp, "ufB-bad"); shutil.copytree(b, bad)
        pth = os.path.join(bad, "tables", "T1.json"); d = json.load(open(pth))
        cell = next(c for c in d["data"][k1]["cells"] if c["count"]); cell["count"] += 1
        json.dump(d, open(pth, "w"))
        v = verify(bad, a); self.assertNotEqual(v.returncode, 0); self.assertIn("FAIL  updates", v.stdout)

        grow(2, c1["id"], 102)                                   # five since A: updated
        c = os.path.join(self.tmp, "ufC"); r = run("C-SYNTHETIC", c, b, "2027-02-28"); self.assertEqual(r.returncode, 0, r.stderr)
        relC = rel(c)
        self.assertNotIn(k1, relC["held"]); self.assertNotIn(kc, relC["held"]); self.assertNotIn("overall", relC["held"])
        self.assertEqual(relC["units"][k1], {"release": "C-SYNTHETIC", "date": "2027-02-28", "leaves": relC["merkle"]["leaves"], "n": c1["count"] + 5, "tier": 1})
        self.assertEqual(load(c, "T1")[k1]["n"], c1["count"] + 5)
        self.assertIsNone(next(x for x in load(c, "T0")["per_compound"] if x["id"] == c1["id"])["tables_as_of"])
        v = verify(c, b); self.assertEqual(v.returncode, 0, v.stdout)
        grow(4, c1["id"], 103)                                   # the store moves on; the release is still verifiable as of itself
        v = verify(c, b); self.assertEqual(v.returncode, 0, v.stdout)

    def test_update_floor_pools_first_publication_and_strata(self):
        """The pool of below-unlock reports follows the rule; a compound's first publication waits
        for five reports newer than the pool's last update; each row of a split table is its own unit."""
        import sqlite3
        db = os.path.join(self.tmp, "up.db"); shutil.copy(self.db, db)
        tax, grow, run, verify, load, rel = self._tools(db)
        count = lambda comp: sqlite3.connect(db).execute("SELECT COUNT(*) FROM reports WHERE compound=?", (comp,)).fetchone()[0]
        a = os.path.join(self.tmp, "upA"); r = run("A-SYNTHETIC", a); self.assertEqual(r.returncode, 0, r.stderr)
        relA = rel(a); t0 = load(a, "T0"); counts = {c["id"]: c for c in t0["per_compound"]}
        classes = json.load(open(tax))["classes"]
        pick = None
        for cls in classes:
            pub = [m for m in cls["members"] if counts[m]["count"] is not None]
            sub = [m for m in cls["members"] if counts[m]["count"] is None and 1 <= count(m) <= 4]
            if pub and sub:
                pick = (cls["id"], pub[0], sub[0]); break
        self.assertIsNotNone(pick); cid, m, s = pick
        kc, kp, ks = f"class:{cid}", f"class:{cid}/pool", f"compound:{s}"
        n_class_A = load(a, "T2")[kc]["n"]

        grow(20, m, 201); grow(2, s, 202)                        # member updates; pool changes by 2
        b = os.path.join(self.tmp, "upB"); r = run("B-SYNTHETIC", b, a, "2027-01-31"); self.assertEqual(r.returncode, 0, r.stderr)
        relB = rel(b)
        self.assertIn(kp, relB["held"]); self.assertEqual(relB["units"][kp], relA["units"][kp])
        self.assertNotIn(kc, relB["held"]); self.assertEqual(load(b, "T2")[kc]["n"], n_class_A + 20)   # the pool's 2 are not in it yet
        v = verify(b, a); self.assertEqual(v.returncode, 0, v.stdout)

        grow(3, s, 203)                                          # pool changed by 5 since A
        c = os.path.join(self.tmp, "upC"); r = run("C-SYNTHETIC", c, b, "2027-02-28"); self.assertEqual(r.returncode, 0, r.stderr)
        relC = rel(c)
        self.assertEqual(relC["units"][kp]["release"], "C-SYNTHETIC"); self.assertEqual(load(c, "T2")[kc]["n"], n_class_A + 25)
        v = verify(c, b); self.assertEqual(v.returncode, 0, v.stdout)

        need = 10 - count(s)                                     # 1..4: reaches unlock with fewer than 5 reports newer than the pool's update
        grow(need, s, 204)
        d = os.path.join(self.tmp, "upD"); r = run("D-SYNTHETIC", d, c, "2027-03-31"); self.assertEqual(r.returncode, 0, r.stderr)
        relD = rel(d)
        self.assertNotIn(ks, relD["units"]); self.assertIn("first publication waits", r.stderr)
        e0 = next(x for x in load(d, "T0")["per_compound"] if x["id"] == s)
        self.assertEqual(e0["count"], 10); self.assertTrue(e0["tables_pending"]); self.assertNotIn(ks, load(d, "T1"))
        grow(5 - need, s, 205)                                   # now five newer than the pool's last update
        e = os.path.join(self.tmp, "upE"); r = run("E-SYNTHETIC", e, d, "2027-04-30"); self.assertEqual(r.returncode, 0, r.stderr)
        relE = rel(e)
        self.assertEqual(relE["units"][ks]["release"], "E-SYNTHETIC"); self.assertEqual(relE["units"][kp]["release"], "E-SYNTHETIC")
        self.assertNotIn(s, relE["units"][kp]["members"])
        v = verify(e, d); self.assertEqual(v.returncode, 0, v.stdout)

        # Strata: one goal row of outcome-by-goal moves on its own count.
        t8 = load(a, "T8")
        g, strata = next((k, [x for x in tab["strata"] if x["n"] is not None]) for k, tab in t8.items() if len([x for x in tab["strata"] if x["n"] is not None]) >= 2)
        gid = g.split(":", 1)[1]; X, Y = strata[0]["goal"], strata[1]["goal"]
        self.assertTrue(all(not k.startswith("class:") for k in t8))                 # never pooled across a class
        self.assertEqual(load(a, "T12")[kc]["stop_reason"]["display"], "not published for a class")
        grow(6, gid, 301, goal=X)
        f = os.path.join(self.tmp, "upF"); r = run("F-SYNTHETIC", f, e, "2027-05-31"); self.assertEqual(r.returncode, 0, r.stderr)
        relF = rel(f)
        self.assertNotIn(f"{g}/T8/{X}", relF["held"]); self.assertIn(f"{g}/T8/{Y}", relF["held"])
        rowY = next(x for x in load(f, "T8")[g]["strata"] if x["goal"] == Y); rowY_A = next(x for x in t8[g]["strata"] if x["goal"] == Y)
        self.assertEqual({k: v for k, v in rowY.items() if k != "as_of"}, rowY_A); self.assertEqual(rowY["as_of"], "A-SYNTHETIC")
        self.assertEqual(next(x for x in load(f, "T8")[g]["strata"] if x["goal"] == X)["n"], strata[0]["n"] + 6)
        v = verify(f, e); self.assertEqual(v.returncode, 0, v.stdout)
        grow(2, gid, 302, goal=Y)
        h = os.path.join(self.tmp, "upG"); r = run("G-SYNTHETIC", h, f, "2027-06-30"); self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn(g, rel(h)["held"]); self.assertIn(f"{g}/T8/{Y}", rel(h)["held"])
        grow(3, gid, 303, goal=Y)
        i2 = os.path.join(self.tmp, "upH"); r = run("H-SYNTHETIC", i2, h, "2027-07-31"); self.assertEqual(r.returncode, 0, r.stderr)
        self.assertNotIn(g, rel(i2)["held"]); self.assertNotIn(f"{g}/T8/{Y}", rel(i2)["held"]); self.assertIn(f"{g}/T8/{X}", rel(i2)["held"])
        v = verify(i2, h); self.assertEqual(v.returncode, 0, v.stdout)

    def test_backdated_exclusion_is_refused(self):
        import sqlite3
        db = os.path.join(self.tmp, "bd.db"); shutil.copy(self.db, db)
        tax, grow, run, verify, load, rel = self._tools(db)
        a = os.path.join(self.tmp, "bdA"); r = run("A-SYNTHETIC", a); self.assertEqual(r.returncode, 0, r.stderr)
        con = sqlite3.connect(db); con.execute("INSERT INTO exclusions (leaf_idx, reason, noted_on) VALUES (1, 'test', '2026-12-15')"); con.commit(); con.close()
        b = os.path.join(self.tmp, "bdB"); r = run("B-SYNTHETIC", b, a, "2027-01-31")
        self.assertNotEqual(r.returncode, 0); self.assertIn("backdated", r.stderr)

    def test_tampered_release_fails_verification(self):
        out = os.path.join(self.tmp, "r4"); self.assertEqual(self.rel("T-SYNTHETIC", out).returncode, 0)
        p = os.path.join(out, "tables", "T1.json"); d = json.load(open(p))
        ent = next(iter(d["data"].values())); ent["cells"][0]["count"] = (ent["cells"][0]["count"] or 0) + 1
        json.dump(d, open(p, "w"))
        v = subprocess.run([self.py, os.path.join(TOOLS, "verify_release.py"), out], capture_output=True, text=True)
        self.assertNotEqual(v.returncode, 0); self.assertIn("FAIL  files", v.stdout)


if __name__ == "__main__":
    unittest.main()
