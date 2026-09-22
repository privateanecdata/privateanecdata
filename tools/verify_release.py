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
  updates      (with --prior) every table release.json lists as held is identical to the prior
               release's, every updated one names this release, and with --db and --taxonomy the
               update-floor decision is re-run on the store as it stood at this release and must
               agree (operator only).
  spec         release.json names the hash of the release specification and taxonomy the release
               was computed under, and they match the copies you have.
  witness      the detached signature on release.json verifies against the published key, and the
               Rekor entry and OpenTimestamps proof, if present, are for this release.json.
  store        (operator only) every stored row's leaf, recomputed with its salt, is in the log,
               and the log's root is the published root — no row was altered after commitment.

None of this proves that any report is truthful or came from a distinct person. It proves that the
published numbers were computed from a fixed, append-only set of reports under a specification
fixed in advance, and that neither has been changed since.
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

ONE_WAY_TABLES = ["T1", "T2", "T3", "T4", "T5", "T6", "T10", "T16"]


def load_tables(rd):
    out = {}
    tdir = os.path.join(rd, "tables")
    if os.path.isdir(tdir):
        for name in os.listdir(tdir):
            if name.endswith(".json"):
                out[name[:-5]] = json.load(open(os.path.join(tdir, name)))["data"]
    return out


def unit_content(T, key):
    """What a unit publishes (tools/update_floor.py): the piece a held unit must carry unchanged.
    Pools publish nothing directly. `as_of` marks are dropped so a fresh row and its later held
    copy compare equal."""
    strip = lambda d: {k: v for k, v in d.items() if k != "as_of"} if isinstance(d, dict) else d
    if key == "overall":
        return {"T6": T.get("T6", {}).get("overall"), "T13": T.get("T13"), "T15": T.get("T15")}
    if key.endswith("/pool") or key == "overall/other":
        return None
    if "/T12/stopped" in key:
        return strip((T.get("T12", {}).get(key.split("/")[0]) or {}).get("stop_reason"))
    if "/T8/" in key:
        g, _, goal = key.partition("/T8/")
        return strip(next((x for x in (T.get("T8", {}).get(g) or {}).get("strata", []) if x.get("goal") == goal), None))
    if "/T11/" in key:
        g, _, eff = key.partition("/T11/")
        return strip(next((x for x in (T.get("T11", {}).get(g) or {}).get("effects", []) if x.get("effect") == eff), None))
    content = {t: T.get(t, {}).get(key) for t in ONE_WAY_TABLES}
    content["T12.status"] = (T.get("T12", {}).get(key) or {}).get("status")
    return content


def check_updates(R, rel, rd, prior, pd, db=None, taxonomy=None):
    """The update floor. Public part: every held unit is identical to the prior release's, every
    fresh record names this release, and a group whose units are all held carries the prior
    release's figures byte for byte. With the store and taxonomy, the decision is re-run on the
    store as it stood at this release and must come out the same."""
    if "units" not in rel:
        R.skip("updates", "release.json carries no unit records (pipeline predates the update floor)")
        return
    units, held = rel["units"], set(rel.get("held", []))
    punits = prior.get("units", {})
    T, P = load_tables(rd), load_tables(pd)
    problems = []
    for key in sorted(held):
        if units.get(key) != punits.get(key):
            problems.append(f"{key}: held, but its record changed")
        if unit_content(T, key) != unit_content(P, key):
            problems.append(f"{key}: held, but its published tables differ from the prior release")
    for key, rec in units.items():
        if key not in held and (rec.get("release") != rel["release"] or rec.get("date") != rel["date"] or rec.get("leaves") != rel["merkle"]["leaves"]):
            problems.append(f"{key}: updated, but its record does not name this release")
    groups = {k for k in units if k.startswith(("compound:", "class:")) and "/" not in k}
    for g in sorted(groups | ({"overall"} if "overall" in units else set())):
        mine = [k for k in units if k == g or k.startswith(g + "/")]
        if all(k in held for k in mine):
            figdir = "figures/_overall/" if g == "overall" else f"figures/{g.replace(':', '-')}/"
            for path, h in prior["files"].items():
                if path.startswith(figdir) and rel["files"].get(path) != h:
                    problems.append(f"{g}: every unit held, but {path} differs from the prior release")
    exact = False
    if db and taxonomy:
        import update_floor as uf
        con = open_store(db)
        rows, leaves = load_rows(con), load_leaves(con)
        attach_leaf_idx(rows, leaves)
        n = rel["merkle"]["leaves"]
        if n > len(leaves):
            problems.append(f"store has {len(leaves)} leaves, fewer than the release's {n}")
        else:
            then = leaves[:n]
            excl = [x for x in load_exclusions(con) if x["noted_on"] <= rel["date"]]
            listed = {x["leaf_idx"] for x in json.load(open(os.path.join(rd, "exclusions.json")))["excluded"]}
            if {x["leaf_idx"] for x in excl} != listed:
                problems.append("exclusions dated on or before the release differ from the release's exclusion list")
            plan = uf.plan(json.load(open(taxonomy)), rows, then, excl, punits, rel["release"], rel["date"])
            if uf.records(plan) != units:
                diff = [k for k in set(uf.records(plan)) | set(units) if uf.records(plan).get(k) != units.get(k)]
                problems.append(f"unit records differ from a re-run of the decision: {sorted(diff)[:6]}")
            if uf.held(plan) != sorted(held):
                problems.append(f"held set differs from a re-run of the decision: {sorted(set(uf.held(plan)) ^ held)[:6]}")
            exact = True
    if problems:
        R.fail("updates", "; ".join(problems[:5]))
    else:
        R.ok("updates", f"{len(held)} held units identical to the prior release"
                        + ("; decision re-run on the store as of this release agrees" if exact else "; pass --db and --taxonomy to re-run the decision"))


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
          f"{rel['counts']['excluded']} excluded, {rel['counts']['analyzed']} analysed")

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
        R.skip("prior", "pass --prior to check append-only continuity and the update floor")

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
