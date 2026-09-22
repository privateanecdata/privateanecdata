# Witness record

This file records, for every witnessed document, the hash submitted to two independent public
logs — and, later, every amendment and every version of the privacy statement and terms. A
version without a row here has not yet been witnessed.

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
