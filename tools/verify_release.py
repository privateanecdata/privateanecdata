#!/usr/bin/env python3
"""
Verify a published release. Anyone can run this on the downloaded release directory; it needs
nothing private.

    python3 tools/verify_release.py releases/2027-Q1
    python3 tools/verify_release.py releases/2027-Q1 --prior releases/2026-Q4
    python3 tools/verify_release.py releases/2027-Q1 --spec spec/RELEASE_SPEC.md --taxonomy spec/taxonomy.v1.json
    python3 tools/verify_release.py releases/2027-Q1 --db data/reports.db        # operator only

What each check proves, and what it does not:

  files        every file named in release.json has the SHA-256 it claims. Together with the
               signature and transparency-log entry on release.json (see --witness), this shows the
               release is the one that was witnessed, unchanged.
  root         the Merkle root in release.json is the root of the published leaf list, and the
               leaf count equals the committed count. The root is what was witnessed; the count is
               therefore the count as of that release.
  prior        the previous release's leaves are a prefix of this one's: nothing was removed,
               reordered or backdated between releases. Chains back to the first release.
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
import shutil
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from pa_store import load_leaves, load_rows, merkle_root, open_store, verify_store  # noqa: E402


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
    else:
        R.skip("prior", "pass --prior to check append-only continuity")

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

    # witness
    wdir = os.path.join(rd, "witness")
    sig = os.path.join(wdir, "release.json.sig")
    pub = args.pubkey or os.path.join(wdir, "pubkey.pem")
    if os.path.exists(sig) and os.path.exists(pub):
        if shutil.which("openssl"):
            r = subprocess.run(["openssl", "dgst", "-sha256", "-verify", pub, "-signature", sig, os.path.join(rd, "release.json")],
                               capture_output=True, text=True)
            (R.ok if r.returncode == 0 else R.fail)("signature", r.stdout.strip() or r.stderr.strip())
        else:
            R.skip("signature", "openssl not found")
        rekor = os.path.join(wdir, "release.json.rekor.json")
        if os.path.exists(rekor):
            entry = json.load(open(rekor))
            want = sha256_file(os.path.join(rd, "release.json"))
            got = entry.get("artifact_sha256")
            (R.ok if got == want else R.fail)("rekor", f"entry {entry.get('log_index')} / {str(entry.get('uuid'))[:16]}… for release.json {want[:16]}…"
                                               + ("" if got == want else f" but entry says {str(got)[:16]}…"))
            print("        confirm independently: rekor-cli get --log-index", entry.get("log_index"))
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
