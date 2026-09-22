# Releases

One directory per release, written by `tools/release.py` and never modified afterwards. A later
release supersedes an earlier one; it does not replace it.

```
releases/
  pubkey.pem                 the release signing key (also in each release's witness/)
  2026-Q4/
    release.json             date, schema and spec hashes, Merkle root, SHA-256 of every file
    tables/T0.json … T15.json
    figures/<compound-or-class>/T*.svg
    exclusions.json          reports omitted from the tables, by log position and reason code
    merkle/leaves.txt        every leaf in log order — recompute the root and the count yourself
    witness/                 release.json.sig, pubkey.pem, release.json.rekor.json, release.json.ots
```

Directories whose name contains `SYNTHETIC` are pipeline tests generated from a synthetic store
(`tools/synth_store.py`) and are ignored by git. The pipeline refuses to write a synthetic release
under any other name, and the site labels them.

Verify any release with `python3 tools/verify_release.py releases/<id>`; see
[docs/HOW-TO-VERIFY.md](../docs/HOW-TO-VERIFY.md).
