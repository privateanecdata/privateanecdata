#!/usr/bin/env python3
"""
Verify a published release. Anyone can run this on the downloaded release directory; it needs
nothing private.

    python3 tools/verify_release.py releases/2026-12
    python3 tools/verify_release.py releases/2026-12 --prior releases/2026-11
    python3 tools/verify_release.py releases/2026-12 --spec spec/RELEASE_SPEC.md --taxonomy spec/taxonomy.v1.json
    python3 tools/verify_release.py releases/2026-12 --db data/reports.db        # operator only

What each check proves, and what it does not:

  files        every file named in release.json has the SHA-256 it claims. Together with the
               signature and transparency-log entry on release.json (see --witness), this shows the
               release is the one that was witnessed, unchanged.
  root         the Merkle root in release.json is the root of the published leaf list, and the
               leaf count equals the committed count. The root is what was witnessed; the count is
               therefore the count as of that release.
  prior        the previous release's leaves are a prefix of this one's: nothing was removed,
               reordered or backdated between releases. Chains back to the first release.
  updates      every table shown names the release that computed it and carries the matching
               as-of mark; a table republished from an earlier release is identical to the prior
               release's, its own figure included; exclusions only grow, keep their dates and are
               never backdated; T0's labels agree. With --db and --taxonomy the batch rule is
               replayed over the whole history from the store and must agree (operator only) —
               that each update was a batch of at least five is checkable only this way.
  spec         release.json names the hash of the release specification and taxonomy the release
               was computed under, and they match the copies you have.
  witness      the detached signature on release.json verifies against the published key, and the
               Rekor entry and OpenTimestamps proof, if present, are for this release.json.
  store        (operator only) every stored row's leaf, recomputed with its salt, is in the log,
               and the log's root is the published root — no row was altered after commitment.

None of this proves that any report is truthful or came from a distinct person. The public checks
show that the published files are the ones that were witnessed, that the log they count is
append-only, and that they name a specification fixed in advance. That the tables were computed
from the stored reports under that specification is shown only by the operator's checks (--db
with --taxonomy: the rule replayed and every file rebuilt from the store).
"""
import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from pa_store import attach_leaf_idx, load_exclusions, load_leaves, load_rows, merkle_root, open_store, verify_store  # noqa: E402

ONE_WAY_TABLES = ["T1", "T2", "T4", "T5", "T6", "T10", "T16"]
TIER_OF_TABLE = {"T1": 1, "T2": 1, "T3": 2, "T4": 2, "T5": 2, "T6": 2, "T10": 2, "T12": 2, "T16": 2, "T8": 3, "T11": 4}


def load_tables(rd):
    out = {}
    tdir = os.path.join(rd, "tables")
    if os.path.isdir(tdir):
        for name in os.listdir(tdir):
            if name.endswith(".json"):
                out[name[:-5]] = json.load(open(os.path.join(tdir, name)))["data"]
    return out


def unit_content(T, key):
    """What one unit publishes (tools/update_floor.py), as (content without `as_of`, the as_of marks
    found, the number of published pieces). A piece that is a placeholder (n is None) is not
    content."""
    pieces = []
    if key == "overall":
        pieces = [("T13", T.get("T13"))]
    elif "/T12/stopped" in key:
        pieces = [("stop", (T.get("T12", {}).get(key.split("/")[0]) or {}).get("stop_reason"))]
    elif "/T8/" in key:
        g, _, goal = key.partition("/T8/")
        pieces = [("row", next((x for x in (T.get("T8", {}).get(g) or {}).get("strata", []) if x.get("goal") == goal), None))]
    elif "/T11/" in key:
        g, _, eff = key.partition("/T11/")
        pieces = [("row", next((x for x in (T.get("T11", {}).get(g) or {}).get("effects", []) if x.get("effect") == eff), None))]
    else:
        t3 = T.get("T3", {}).get(key) or {}
        pieces = [(t, T.get(t, {}).get(key)) for t in ONE_WAY_TABLES] + [("T12.status", (T.get("T12", {}).get(key) or {}).get("status"))]
        # T3 is two distributions under one wrapper that carries the mark
        for part in ("start_dose", "current_dose"):
            if isinstance(t3.get(part), dict):
                pieces.append((f"T3.{part}", {**t3[part], **({"as_of": t3["as_of"]} if "as_of" in t3 else {})}))
    content, marks, n = {}, [], 0
    for name, d in pieces:
        if not isinstance(d, dict) or d.get("n") is None:
            continue
        n += 1
        content[name] = {k: v for k, v in d.items() if k != "as_of"}
        if "as_of" in d:
            marks.append(d["as_of"])
    return content, marks, n


def unit_figures(key):
    """The figure paths that belong to one unit (a T8 grid belongs to no single unit)."""
    if key == "overall":
        return ["figures/_overall/"]
    if "/T8/" in key:
        return []
    if "/T12/stopped" in key:
        return [f"figures/{key.split('/')[0].replace(':', '-')}/T12-stop_reason.svg"]
    if "/T11/" in key:
        g, _, eff = key.partition("/T11/")
        d = g.replace(":", "-")
        return [f"figures/{d}/T11-{eff}-onset.svg", f"figures/{d}/T11-{eff}-dechallenge.svg"]
    d = key.replace(":", "-")
    return [f"figures/{d}/{n}.svg" for n in ("T1", "T2", "T3-start_dose", "T3-current_dose", "T4", "T5", "T6", "T10", "T12-status", "T16")]


def check_updates(R, rel, rd, prior, pd, db=None, taxonomy=None):
    """The update floor. Public part: every shown unit's record names this release (updated) or an
    earlier one (republished), and its tables carry the matching `as_of` marks; a republished unit
    the prior release also showed is identical to it, figure included; the history chains to the
    prior release; exclusions only grow, keep their dates and are never backdated; T0's labels
    agree with the records. With the store and taxonomy, the rule is replayed over the whole history
    and must give the same records and the same republished set. That each update was a batch of at
    least five can only be checked this way: the public files do not show it."""
    if "units" not in rel:
        R.skip("updates", "release.json carries no unit records (pipeline predates the update floor)")
        return
    units, held = rel["units"], set(rel.get("held", []))
    T = load_tables(rd)
    problems, notes = [], []
    first = not rel["merkle"].get("prior_root")
    if first and (held or rel.get("history")):
        problems.append("a first release republishes nothing and has no history")
    if not held <= set(units):
        problems.append(f"held lists units with no record: {sorted(held - set(units))[:4]}")
    for key, rec in units.items():
        if set(rec) - {"release", "date", "tier"}:
            problems.append(f"{key}: record carries more than release, date and tier: {sorted(set(rec) - {'release', 'date', 'tier'})}")
        content, marks, n = unit_content(T, key)
        if n == 0:
            problems.append(f"{key}: has a record but publishes nothing")
        if key in held:
            if rec.get("release") == rel["release"]:
                problems.append(f"{key}: listed as republished but its record names this release")
            if len(marks) != n or any(m != rec.get("release") for m in marks):
                problems.append(f"{key}: republished, but its tables are not all marked as of {rec.get('release')}")
        else:
            if rec.get("release") != rel["release"] or rec.get("date") != rel["date"]:
                problems.append(f"{key}: not listed as republished, but its record names {rec.get('release')}")
            if marks:
                problems.append(f"{key}: updated in this release but its tables carry an as-of mark")
    # Every published piece belongs to a unit with a record, at a tier that allows it.
    for tid in ONE_WAY_TABLES + ["T3", "T12", "T8", "T11"]:
        for key, v in (T.get(tid) or {}).items():
            rec = units.get(key)
            if rec is None:
                problems.append(f"{tid} publishes {key}, which has no record"); continue
            if (rec.get("tier") or 0) < TIER_OF_TABLE[tid]:
                problems.append(f"{tid} publishes {key} at tier {rec.get('tier')}, below the tier the table needs")
            if tid == "T8":
                for st in v.get("strata", []):
                    if st.get("n") is not None and f"{key}/T8/{st['goal']}" not in units:
                        problems.append(f"T8 publishes a row for {key}/{st['goal']} with no record")
            if tid == "T11":
                for ef in v.get("effects", []):
                    if ef.get("n") is not None and f"{key}/T11/{ef['effect']}" not in units:
                        problems.append(f"T11 publishes a row for {key}/{ef['effect']} with no record")
            if tid == "T12" and (v.get("stop_reason") or {}).get("n") is not None and f"{key}/T12/stopped" not in units:
                problems.append(f"T12 publishes a stop-reason row for {key} with no record")
    if (T.get("T13") or {}).get("n") is not None and "overall" not in units:
        problems.append("T13 is published with no record for the all-reports unit")
    for g, t9 in (T.get("T9") or {}).items():
        for part in t9.get("compounds", []):
            row = next((x for x in (T.get("T8", {}).get(f"compound:{part['compound']}") or {}).get("strata", []) if x.get("goal") == g), None)
            if row is None or any(row.get(k) != part.get(k) for k in ("n", "percent", "cells", "as_of")):
                problems.append(f"T9 {g}: the row for {part['compound']} is not its T8 row")
    ex_now = json.load(open(os.path.join(rd, "exclusions.json")))["excluded"]
    if any(x["noted_on"] > rel["date"] for x in ex_now):
        problems.append("an exclusion is dated after the release")
    uncompared = []
    if prior is not None:
        want_hist = prior.get("history", []) + [{"release": prior["release"], "date": prior["date"], "leaves": prior["merkle"]["leaves"]}]
        if rel.get("history") != want_hist:
            problems.append("history does not chain to the prior release")
        punits = prior.get("units", {})
        P = load_tables(pd)
        for key in sorted(held & set(units)):
            prec = punits.get(key)
            if prec is None:
                uncompared.append(key)        # not shown in the prior release: nothing to compare with
                continue
            if prec != units[key]:
                problems.append(f"{key}: republished, but the prior release showed it computed in {prec.get('release')}")
                continue
            if unit_content(T, key)[0] != unit_content(P, key)[0]:
                problems.append(f"{key}: republished, but its tables differ from the prior release")
            for path in unit_figures(key):
                if path.endswith("/"):
                    same = all(rel["files"].get(q) == h for q, h in prior["files"].items() if q.startswith(path))
                else:
                    same = path not in prior["files"] or rel["files"].get(path) == prior["files"][path]
                if not same:
                    problems.append(f"{key}: republished, but its figure {path} differs from the prior release")
        triple = lambda x: (x["leaf_idx"], x["reason"], x["noted_on"])
        pex = {triple(x) for x in json.load(open(os.path.join(pd, "exclusions.json")))["excluded"]}
        ex = {triple(x) for x in ex_now}
        if not pex <= ex:
            problems.append("an exclusion listed by the prior release is missing or carries a different reason or date")
        if any(t[2] <= prior["date"] for t in ex - pex):
            problems.append("an exclusion new to this release is dated on or before the prior release (backdated)")
    if uncompared:
        notes.append(f"{len(uncompared)} republished unit(s) the prior release did not show, so not compared with it")
    # T0 labels agree with the records
    for e in T.get("T0", {}).get("per_compound", []):
        if e["id"] == "other":
            continue
        key = "compound:" + e["id"]
        rec = units.get(key)
        if e.get("tier") != (rec or {}).get("tier", 0):
            problems.append(f"{key}: T0 tier {e.get('tier')} does not match its record")
        if e.get("tables_as_of") != ((rec or {}).get("release") if key in held else None):
            problems.append(f"{key}: T0 tables_as_of does not match its record")
        if rel.get("tiers", {}).get(key) != e.get("tier"):
            problems.append(f"{key}: release.json tiers disagrees with T0")
    exact = False
    if db and taxonomy:
        import release as rp
        import update_floor as uf
        con = open_store(db)
        rows, leaves = load_rows(con), load_leaves(con)
        attach_leaf_idx(rows, leaves)
        n = rel["merkle"]["leaves"]
        if n > len(leaves):
            problems.append(f"store has {len(leaves)} leaves, fewer than the release's {n}")
        else:
            excl = [x for x in load_exclusions(con) if x["noted_on"] <= rel["date"]]
            triple = lambda x: (x["leaf_idx"], x["reason"], x["noted_on"])
            if {triple(x) for x in excl} != {triple(x) for x in ex_now}:
                problems.append("the store's exclusions dated on or before the release differ from the release's list")
            tax = rp.Tax(taxonomy)
            plan = uf.plan(tax.raw, rows, leaves[:n], excl, rel.get("history", []), rel["release"], rel["date"], rp.shown_fn(tax))
            want = uf.records(plan)
            if want != units:
                diff = [k for k in set(want) | set(units) if want.get(k) != units.get(k)]
                problems.append(f"unit records differ from a replay of the rule: {sorted(diff)[:6]}")
            if uf.held(plan) != sorted(held):
                problems.append(f"republished set differs from a replay of the rule: {sorted(set(uf.held(plan)) ^ held)[:6]}")
            exact = True
            # Rebuild: the pipeline is deterministic, so re-running it on the store as it stood
            # must reproduce every published file. Only meaningful with the same pipeline code.
            here = os.path.dirname(os.path.abspath(__file__))
            if (rel.get("pipeline", {}).get("sha256") != sha256_file(os.path.join(here, "release.py"))
                    or rel.get("pipeline", {}).get("update_floor_sha256") != sha256_file(os.path.join(here, "update_floor.py"))):
                notes.append("rebuild skipped: this release was made by a different tools/release.py")
            elif not first and prior is None:
                notes.append("rebuild skipped: pass --prior to rebuild a release that has one")
            else:
                rebuilt = rebuild(rel, db, taxonomy, pd, n)
                if isinstance(rebuilt, str):
                    problems.append(f"rebuild failed: {rebuilt}")
                else:
                    diff = sorted(f for f in set(rebuilt) | set(rel["files"]) if rebuilt.get(f) != rel["files"].get(f))
                    if diff:
                        problems.append(f"rebuilding from the store gives different files: {diff[:4]}")
                    else:
                        notes.append("every file rebuilt from the store is identical")
    if problems:
        R.fail("updates", "; ".join(problems[:5]))
    else:
        R.ok("updates", "; ".join([(f"{len(held) - len(uncompared)} republished units identical to the prior release" if prior is not None
                                    else ("first release: every table computed in it" if first else f"{len(held)} republished units marked; pass --prior to compare them"))]
                                  + notes
                                  + (["rule replayed from the store over the whole history agrees"] if exact else ["pass --db and --taxonomy to replay the rule"])))


def rebuild(rel, db, taxonomy, prior_dir, n_leaves):
    """Re-run tools/release.py on a copy of the store truncated to this release's log and
    exclusions, and return {path: sha256} of what it writes, or an error string."""
    import sqlite3
    import tempfile
    tmp = tempfile.mkdtemp()
    try:
        copy = os.path.join(tmp, "store.db")
        src = sqlite3.connect(f"file:{db}?mode=ro", uri=True); dst = sqlite3.connect(copy)
        src.backup(dst); src.close()
        dst.execute("DELETE FROM exclusions WHERE noted_on > ?", (rel["date"],))
        keep = [r[0] for r in dst.execute("SELECT idx FROM merkle_leaves ORDER BY idx LIMIT ?", (n_leaves,))]
        if len(keep) == n_leaves:
            cut = keep[-1] if keep else 0
            gone = [bytes(r[0]) for r in dst.execute("SELECT leaf FROM merkle_leaves WHERE idx > ?", (cut,))]
            dst.execute("DELETE FROM merkle_leaves WHERE idx > ?", (cut,))
            # drop the rows whose leaves were cut (rows carry no log position; match by leaf)
            from pa_store import row_leaf
            gone = set(gone)
            dst.row_factory = sqlite3.Row
            rows = load_rows(dst)
            con2 = dst
            for r in rows:
                if row_leaf(r) in gone:
                    con2.execute("DELETE FROM reports WHERE salt = ?", (r["_salt"],))
        dst.commit(); dst.close()
        out = os.path.join(tmp, "out")
        cmd = [sys.executable, os.path.join(os.path.dirname(os.path.abspath(__file__)), "release.py"), "--db", copy,
               "--id", rel["release"], "--date", rel["date"], "--out", out, "--taxonomy", taxonomy]
        cmd += ["--prior", prior_dir] if prior_dir else ["--first"]
        r = subprocess.run(cmd, capture_output=True, text=True)
        if r.returncode != 0:
            return (r.stderr or r.stdout).strip().splitlines()[-1] if (r.stderr or r.stdout).strip() else "release.py failed"
        return json.load(open(os.path.join(out, "release.json")))["files"]
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 16), b""):
            h.update(chunk)
    return h.hexdigest()


def read_leaves(path):
    return [l.strip() for l in open(path) if l.strip()]


class Report:
    def __init__(self):
        self.failed = False

    def ok(self, name, detail=""):
        print(f"  ok    {name}" + (f"  — {detail}" if detail else ""))

    def fail(self, name, detail=""):
        self.failed = True
        print(f"  FAIL  {name}" + (f"  — {detail}" if detail else ""))

    def skip(self, name, detail=""):
        print(f"  skip  {name}" + (f"  — {detail}" if detail else ""))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("release", help="release directory containing release.json")
    ap.add_argument("--prior", help="previous release directory, to check the log is append-only")
    ap.add_argument("--spec", help="RELEASE_SPEC.md to compare against the hash in release.json")
    ap.add_argument("--taxonomy", help="taxonomy.v1.json to compare against the hash in release.json")
    ap.add_argument("--pubkey", help="PEM public key to verify release.json.sig (default: witness/pubkey.pem in the release)")
    ap.add_argument("--db", help="operator only: the private store, to check rows against the log")
    args = ap.parse_args()

    R = Report()
    rd = args.release
    rel = json.load(open(os.path.join(rd, "release.json")))
    print(f"release {rel['release']} dated {rel['date']} — {rel['counts']['committed']} committed, "
          f"{rel['counts']['excluded']} excluded, {rel['counts']['analyzed']} not excluded")

    # files
    bad, missing = [], []
    for path, want in rel["files"].items():
        full = os.path.join(rd, path)
        if not os.path.exists(full):
            missing.append(path)
        elif sha256_file(full) != want:
            bad.append(path)
    listed = set(rel["files"]) | {"release.json"}
    extra = []
    for dirpath, _, names in os.walk(rd):
        for n in names:
            p = os.path.relpath(os.path.join(dirpath, n), rd)
            if p not in listed and not p.startswith("witness" + os.sep) and p != "witness":
                extra.append(p)
    if bad or missing:
        R.fail("files", f"{len(bad)} changed, {len(missing)} missing: {(bad + missing)[:5]}")
    else:
        R.ok("files", f"{len(rel['files'])} files match release.json")
    if extra:
        R.fail("files", f"not listed in release.json: {extra[:5]}")

    # root
    leaves = read_leaves(os.path.join(rd, rel["merkle"]["leaves_file"]))
    root = merkle_root([bytes.fromhex(l) for l in leaves]).hex()
    if len(leaves) != rel["merkle"]["leaves"] or len(leaves) != rel["counts"]["committed"]:
        R.fail("root", f"leaf list has {len(leaves)} entries; release.json says {rel['merkle']['leaves']} / committed {rel['counts']['committed']}")
    elif root != rel["merkle"]["root"]:
        R.fail("root", f"recomputed {root[:16]}… ≠ published {rel['merkle']['root'][:16]}…")
    else:
        R.ok("root", f"{root[:16]}… over {len(leaves)} leaves")

    # prior
    if args.prior:
        prior = json.load(open(os.path.join(args.prior, "release.json")))
        pl = read_leaves(os.path.join(args.prior, prior["merkle"]["leaves_file"]))
        if rel["merkle"].get("prior_root") != prior["merkle"]["root"]:
            R.fail("prior", "release.json's prior_root is not the prior release's root")
        elif leaves[: len(pl)] != pl:
            R.fail("prior", "prior leaves are not a prefix of this release's leaves — the log was not append-only")
        else:
            R.ok("prior", f"{prior['release']} ({len(pl)} leaves) is a prefix; {len(leaves) - len(pl)} appended since")
        check_updates(R, rel, rd, prior, args.prior, args.db, args.taxonomy)
    else:
        R.skip("prior", "pass --prior to check append-only continuity")
        check_updates(R, rel, rd, None, None, args.db, args.taxonomy)

    # spec and taxonomy
    if args.spec:
        h = sha256_file(args.spec)
        (R.ok if h == rel["release_spec"]["sha256"] else R.fail)("spec", f"RELEASE_SPEC.md {h[:16]}… v{rel['release_spec']['version']}")
    else:
        R.skip("spec", "pass --spec to compare the release specification's hash")
    if args.taxonomy:
        h = sha256_file(args.taxonomy)
        (R.ok if h == rel["taxonomy_sha256"] else R.fail)("taxonomy", f"taxonomy {h[:16]}… schema {rel['schema_version']}")
    else:
        R.skip("taxonomy", "pass --taxonomy to compare the schema's hash")
    # nothing but the enumerated artifacts may ship
    ALLOWED = re.compile(r"^(release\.json|tables/T\d+\.json|figures/[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+\.svg|exclusions\.json|merkle/leaves\.txt|witness/[A-Za-z0-9_.-]+)$")
    odd = [p for p in extra + list(rel["files"]) if not ALLOWED.match(p)]
    if odd:
        R.fail("files", f"not an enumerated artifact: {odd[:5]}")

    # witness. Everything under witness/ ships with the release, so on its own it proves nothing:
    # a tampered copy can carry its own key and its own rekor.json. The signature counts only
    # against a key you obtained independently (--pubkey), and the Rekor entry only when the
    # public log is queried.
    wdir = os.path.join(rd, "witness")
    WITNESS_FILES = {"release.json.sig", "pubkey.pem", "release.json.rekor.json", "release.json.ots"}
    if os.path.isdir(wdir):
        stray = sorted(set(os.listdir(wdir)) - WITNESS_FILES)
        if stray:
            R.fail("files", f"unexpected files under witness/: {stray[:5]}")
    sig = os.path.join(wdir, "release.json.sig")
    if os.path.exists(sig):
        if not args.pubkey:
            R.skip("signature", "present, but not checked: pass --pubkey with a copy of the key obtained elsewhere "
                                "(the repository's releases/pubkey.pem, or a key you have seen before); the copy inside the release proves nothing")
        elif shutil.which("openssl"):
            r = subprocess.run(["openssl", "dgst", "-sha256", "-verify", args.pubkey, "-signature", sig, os.path.join(rd, "release.json")],
                               capture_output=True, text=True)
            (R.ok if r.returncode == 0 else R.fail)("signature", r.stdout.strip() or r.stderr.strip())
        else:
            R.skip("signature", "openssl not found")
        rekor = os.path.join(wdir, "release.json.rekor.json")
        if os.path.exists(rekor):
            entry = json.load(open(rekor))
            want = sha256_file(os.path.join(rd, "release.json"))
            idx = entry.get("log_index")
            if entry.get("artifact_sha256") != want:
                R.fail("rekor", f"witness/release.json.rekor.json is for {str(entry.get('artifact_sha256'))[:16]}…, not this release.json ({want[:16]}…)")
            elif shutil.which("rekor-cli") and idx is not None:
                r = subprocess.run(["rekor-cli", "get", "--log-index", str(idx), "--format", "json"], capture_output=True, text=True)
                found = r.returncode == 0 and want in r.stdout
                (R.ok if found else R.fail)("rekor", f"public log entry {idx} " + ("carries this release.json's hash" if found else "does not carry this hash or could not be fetched"))
            else:
                R.skip("rekor", f"claims log index {idx}; not checked against the public log (install rekor-cli, or open "
                                f"https://search.sigstore.dev/?logIndex={idx} and compare the hash {want[:16]}…)")
        else:
            R.skip("rekor", "no witness/release.json.rekor.json")
        ots = os.path.join(rd, "witness", "release.json.ots")
        if os.path.exists(ots):
            if shutil.which("ots"):
                r = subprocess.run(["ots", "verify", "-f", os.path.join(rd, "release.json"), ots], capture_output=True, text=True)
                (R.ok if r.returncode == 0 else R.fail)("opentimestamps", (r.stdout + r.stderr).strip().splitlines()[-1] if (r.stdout + r.stderr).strip() else "")
            else:
                R.skip("opentimestamps", "ots client not found; proof file present")
        else:
            R.skip("opentimestamps", "no witness/release.json.ots")
    else:
        R.skip("witness", "no signature yet (tools/witness.sh not run)")
    ots = os.path.join(wdir, "release.json.ots")
    if os.path.exists(ots) and not os.path.exists(sig):
        R.skip("opentimestamps", "proof present without a signature")

    # store (operator)
    if args.db:
        con = open_store(args.db)
        v = verify_store(load_rows(con), load_leaves(con))
        if not v["ok"]:
            R.fail("store", json.dumps(v))
        elif v["leaves"] < rel["merkle"]["leaves"]:
            R.fail("store", f"store has {v['leaves']} leaves, fewer than the release's {rel['merkle']['leaves']}")
        else:
            db_leaves = [l.hex() for _, l in load_leaves(con)]
            if db_leaves[: len(leaves)] != leaves:
                R.fail("store", "published leaves are not a prefix of the store's log")
            else:
                R.ok("store", f"{v['rows']} rows all present in the log; published leaves are a prefix of the store's log")

    print("\nRESULT:", "FAILED" if R.failed else "verified")
    sys.exit(1 if R.failed else 0)


if __name__ == "__main__":
    main()
