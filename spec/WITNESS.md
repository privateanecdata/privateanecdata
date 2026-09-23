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
| `spec/RELEASE_SPEC.md` | 1.0 | `2ef2f1e6a8da3153cb520c348796aa753bd0c199a50281f5884ebf61a3153dd3` | [2925396720](https://search.sigstore.dev/?logIndex=2925396720) | `108e9186e8c5677ad2df6a9d01a3b8a71be5ea0e3d91b6afc84714d42520f41181c17cccfcc2d8b5` | [RELEASE_SPEC.md.ots](witness/RELEASE_SPEC.md.ots) — pending; upgrade due 2026-09-24 | 2026-09-23 |
| `spec/taxonomy.v1.json` | 1.0 | `1bbf7e563e1efbc72307d3004f84f6f69b3f4f79108b0f532d7c5664d76c30e2` | [2925397015](https://search.sigstore.dev/?logIndex=2925397015) | `108e9186e8c5677a90ce3336f280dad93664d355ea9778bd9a3e66909a4e87bfb3f33922c4912550` | [taxonomy.v1.json.ots](witness/taxonomy.v1.json.ots) — pending; upgrade due 2026-09-24 | 2026-09-23 |
| `spec/SCHEMA.md` | 1.0 | `9af62ce212e717e9ac51970f9abc8fb32e437b683321b7287ef157143099fb15` | [2925397331](https://search.sigstore.dev/?logIndex=2925397331) | `108e9186e8c5677a3d922333e7be791d51cf779a40a7fb9f9cb13ca642b061e3ee20bebcaea762e1` | [SCHEMA.md.ots](witness/SCHEMA.md.ots) — pending; upgrade due 2026-09-24 | 2026-09-23 |
| `docs/PRIVACY.md` | 1.0 | `63d35d5778387b653c8d58bd589a03599541cb6e2f213f74bb56e514dd0d1b66` | [2925397412](https://search.sigstore.dev/?logIndex=2925397412) | `108e9186e8c5677a179f32c136697ccff89442968303da5c01e318465a556e527c4cf5e3b29584c1` | [PRIVACY.md.ots](../docs/witness/PRIVACY.md.ots) — pending; upgrade due 2026-09-24 | 2026-09-23 |
| `docs/TERMS.md` | 1.0 | `344499d565c3fe7f1f469e4c3da355185f3ad52910d9fe90b9e8dbbb01a552c6` | [2925397479](https://search.sigstore.dev/?logIndex=2925397479) | `108e9186e8c5677aa84f62055f305de83f885e032eda126b95a46485ae63546c0b7ea3680d0da546` | [TERMS.md.ots](../docs/witness/TERMS.md.ots) — pending; upgrade due 2026-09-24 | 2026-09-23 |

Rekor entries are permanent and public. Only hashes go in. Test on a throwaway file first.
