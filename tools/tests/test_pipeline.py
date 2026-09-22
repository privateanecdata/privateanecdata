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
                    start_dose="b1", current_dose="b1", frequency="daily", titration="no-change", duration="1-3mo",
                    purity_tested="no", reconstitution="bac-water-refrigerated", status="still-taking", stop_reason=None,
                    outcome="slight", adverse_effects="[]", age_band=None, sex=None)
        base.update(kw); return base

    def test_consistent_row_is_clean(self):
        self.assertEqual(detect.check_implausible(self.row()), [])

    def test_duration_status_contradiction(self):
        self.assertTrue(detect.check_implausible(self.row(duration="under-2wk", status="stopped-over-12wk", stop_reason="cost")))

    def test_overlapping_ranges_are_fine(self):
        self.assertEqual(detect.check_implausible(self.row(duration="1-3mo", status="stopped-over-12wk", stop_reason="cost")), [])

    def test_onset_after_duration(self):
        ae = json.dumps([{"id": "headache", "onset": "after-6wk", "dechallenge": "still-taking"}])
        self.assertTrue(detect.check_implausible(self.row(duration="2-4wk", adverse_effects=ae)))

    def test_titration_vs_bands(self):
        self.assertTrue(detect.check_implausible(self.row(titration="no-change", current_dose="b2")))
        self.assertTrue(detect.check_implausible(self.row(titration="stepped-down", current_dose="b3")))
        self.assertEqual(detect.check_implausible(self.row(titration="stepped-up", current_dose="b3")), [])


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

    def test_synthetic_store_needs_synthetic_name(self):
        self.assertNotEqual(self.rel("2026-Q4", os.path.join(self.tmp, "r2")).returncode, 0)

    def test_tampered_store_is_refused(self):
        import sqlite3
        bad = os.path.join(self.tmp, "bad.db"); shutil.copy(self.db, bad)
        con = sqlite3.connect(bad); con.execute("UPDATE reports SET outcome='large' WHERE rowid=(SELECT rowid FROM reports LIMIT 1)"); con.commit(); con.close()
        r = subprocess.run([self.py, os.path.join(TOOLS, "release.py"), "--db", bad, "--id", "X-SYNTHETIC", "--date", "2026-12-31",
                            "--out", os.path.join(self.tmp, "r3"), "--force"], capture_output=True, text=True)
        self.assertNotEqual(r.returncode, 0); self.assertIn("FAILED", r.stderr + r.stdout)

    def test_tampered_release_fails_verification(self):
        out = os.path.join(self.tmp, "r4"); self.assertEqual(self.rel("T-SYNTHETIC", out).returncode, 0)
        p = os.path.join(out, "tables", "T1.json"); d = json.load(open(p))
        ent = next(iter(d["data"].values())); ent["cells"][0]["count"] = (ent["cells"][0]["count"] or 0) + 1
        json.dump(d, open(p, "w"))
        v = subprocess.run([self.py, os.path.join(TOOLS, "verify_release.py"), out], capture_output=True, text=True)
        self.assertNotEqual(v.returncode, 0); self.assertIn("FAIL  files", v.stdout)


if __name__ == "__main__":
    unittest.main()
