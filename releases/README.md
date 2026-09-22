# Releases

One directory per release, written by `tools/release.py` and never modified afterwards. A later
release supersedes an earlier one; it does not replace it.

```
releases/
  pubkey.pem                 the release signing key (also in each release's witness/)
  2026-11/                   ids are YYYY-MM while monthly (the first year), YYYY-QN after
    release.json             date, schema and spec hashes, Merkle root, SHA-256 of every file,
                             and per table the release that computed it (tables update in batches)
    tables/T0.json … T15.json
    figures/<compound-or-class>/T*.svg
    exclusions.json          reports omitted from the tables, by log position and reason code
    merkle/leaves.txt        every leaf in log order — recompute the root and the count yourself
    witness/                 release.json.sig, pubkey.pem, release.json.rekor.json, release.json.ots
```

Directories whose name contains `SYNTHETIC` are generated from a synthetic store
(`tools/synth_store.py`); the pipeline refuses to write a synthetic release under any other name,
and the site labels them. They are ignored by git except `EXAMPLE-SYNTHETIC/`, which is committed
so the site can show what a release looks like before any real one exists. Regenerate it with:

```
python3 tools/synth_store.py /tmp/example.db --n 1500 --seed 42
python3 tools/release.py --db /tmp/example.db --id EXAMPLE-SYNTHETIC --date 2026-12-31 --out releases/EXAMPLE-SYNTHETIC --force
```

Verify any release with `python3 tools/verify_release.py releases/<id>`; see
[docs/RELEASE-SPEC-SUMMARY.md](../docs/RELEASE-SPEC-SUMMARY.md#how-we-count).
