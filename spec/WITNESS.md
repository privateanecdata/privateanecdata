# Witness record

**Empty until the freeze.** This file records, for every frozen document, the hash that was
submitted to two independent public logs before the first report was accepted — and, later, for
every amendment and every version of the privacy statement and terms. Until a row appears here
for a document, that document is a draft.

Procedure, per document (see `tools/witness.sh`):

```
tools/witness.sh all spec/RELEASE_SPEC.md      # signature, Rekor entry, OpenTimestamps stamp
tools/witness.sh all spec/taxonomy.v1.json
tools/witness.sh all docs/PRIVACY.md
tools/witness.sh all docs/TERMS.md
# a day later:
tools/witness.sh upgrade spec/RELEASE_SPEC.md   # etc. — the .ots proof must be upgraded
```

Artifacts land in `spec/witness/` and `docs/witness/`. Commit them with this file. The public key
is `releases/pubkey.pem`.

| Document | Version | SHA-256 | Rekor log index | Rekor UUID | OTS | Date |
|---|---|---|---|---|---|---|
| `spec/RELEASE_SPEC.md` | | | | | | |
| `spec/taxonomy.v1.json` | | | | | | |
| `spec/SCHEMA.md` | | | | | | |
| `docs/PRIVACY.md` | | | | | | |
| `docs/TERMS.md` | | | | | | |

Rekor entries are permanent and public. Only hashes go in. Test on a throwaway file first.
