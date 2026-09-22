# How to verify a release yourself

Every release is a directory of static files. You can check, without trusting us, that the files
you are looking at are the ones we published, that the count of reports is the count we committed
to, that no report was removed or backdated between releases, and that the tables were computed
under a specification fixed before the data existed. You need Python 3, the release directory,
and — for the two external witnesses — `openssl`, `rekor-cli` and `ots`.

What this cannot verify is stated at the end. Read that too.

## The one command

```
python3 tools/verify_release.py releases/2027-Q1 --prior releases/2026-Q4 \
    --spec spec/RELEASE_SPEC.md --taxonomy spec/taxonomy.v1.json
```

`tools/verify_release.py` is in the public repository, is short, and reads nothing but the files
you give it. Each line of its output corresponds to one of the checks below. The rest of this page
explains what each check proves so you can do it by hand if you prefer.

## 1. The files are the files

`release.json` lists the SHA-256 of every other file in the release. Recompute any of them:

```
sha256sum releases/2027-Q1/tables/T8.json
```

and compare with the entry in `release.json`. If they match, that table is byte-for-byte what was
signed and witnessed.

## 2. The count is the count

Every accepted report is committed to an append-only log. Each entry in the log is a hash of the
report together with a secret per-report salt; the entries reveal nothing about the reports, and
the salt is never published, so no one — including the person who submitted it — can find a
particular report in the log. `merkle/leaves.txt` is the full list of entries at release time,
one per line. The Merkle root over that list is in `release.json`, and the root is what is
signed and witnessed.

To check: the number of lines in `leaves.txt` is the committed count in `release.json` and in table
T0; and the root recomputed from the lines equals the published root. The tree is the RFC 6962
construction — interior node = SHA-256(0x01 ‖ left ‖ right), a lone right-hand node promoted — and
`tools/pa_store.py` has it in twenty lines.

## 3. Nothing was removed or backdated

Take the previous release's `leaves.txt`. It must be an exact prefix of this release's. If it is,
every report committed as of the previous release is still there, in the same position, and
everything since was appended after it. `release.json` also records the previous release's root as
`prior_root`, so the chain can be followed back to the first release.

## 4. The rules were fixed first

`release.json` carries the SHA-256 of `spec/RELEASE_SPEC.md` and of `spec/taxonomy.v1.json` as
they stood when the release was computed. `spec/WITNESS.md` records the transparency-log entries
for those documents, submitted before the first report was accepted. If the hashes match, the
tables were computed under rules that predate the data.

## 5. The release was witnessed

`witness/release.json.sig` is a detached signature on `release.json` under the key in
`witness/pubkey.pem` (also at `/releases/pubkey.pem`, and in the repository):

```
openssl dgst -sha256 -verify witness/pubkey.pem -signature witness/release.json.sig release.json
```

`witness/release.json.rekor.json` names the entry in the Sigstore Rekor public transparency log holding that
hash and signature. Confirm it exists and matches, without us in the loop:

```
rekor-cli get --log-index <log_index>
```

`witness/release.json.ots` is an OpenTimestamps proof anchoring the hash of `release.json` in the
Bitcoin blockchain:

```
ots verify -f release.json witness/release.json.ots
```

Two independent logs, neither operated by us, each showing the hash existed no later than the
recorded time. A release cannot later be quietly replaced: the replacement would not match the
witnessed hash.

## What none of this proves

- **That any report is true.** Nothing can. A fabricated report is committed as faithfully as an
  honest one. What is guaranteed is that whatever was committed was counted, and nothing was
  altered afterwards.
- **That reports came from different people.** No identifier exists, so no proof of distinctness
  can. The integrity log (table T14) publishes what the coordinated-submission detector found;
  read it.
- **That a report was not dropped before commitment.** The log proves what happened after a report
  entered it. The insertion policy is published: every submission that passes validation and the
  honeypot is committed, in the same transaction that stores it, with nothing held in between.
  You have to take that on the code, which is public, and on the named operator.
- **That the published tables are the only computation that was run.** The specification lists
  every table that will ever be published. Anything else computed privately is, by definition,
  not published — and the specification cannot be extended without a witnessed amendment one
  release period in advance.
