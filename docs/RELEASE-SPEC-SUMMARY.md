# Release spec

Every report we count is in a public log. Every table we publish, and the number of reports it
needs first, is written down below. This page is the short version first and the full
specification after it.

## What is published, and when {#what-is-published}

Only aggregate statistics. Individual reports are never displayed, shared, licensed, or given to
researchers, in any form.

**Thresholds.** What is published about a compound depends on how many people have reported on
it, so the number of published figures never gets close to the number of reports behind them
([tiers](#tiers)):

- **Under 10 reports:** nothing under the compound's own name. It is counted with the other
  compounds in its class.
- **10 or more:** its report count, route of administration, and source type.
- **50 or more:** intended purpose, dose ranges, frequency, duration, purity testing, side effects,
  and whether people are still taking it, finished, or stopped early.
- **100 or more:** outcome by goal — of the people who took it hoping for X, how many reported no
  change, slight, moderate, or large improvement ([T8](#t8)).
- **200 or more:** when each side effect started and whether it stopped; and percentages, with
  95% confidence intervals, added beside the counts for everything above. (Below 200 a percentage
  would mislead: on 40 reports its interval spans twenty points.)
- **1,000 or more:** outcome by goal shown side by side with other compounds used for the same
  goal ([T9](#t9)). Compounds are never combined into one number and never ranked.

**Small groups are hidden.** Any figure under 5 reports is hidden, and one neighbouring figure is
hidden with it so the small one cannot be worked out by subtraction; both are labelled "not
shown" ([cell rules](#tiers)).
Age and sex are reported only as totals across all contributors, never with any other answer.

**Never.** No ranking, no "most effective," no comparison statistic between compounds, no
average of any scale, no per-vendor or per-region breakdown, no individual row, no live count,
no statistic on request ([the full list](#never); [analyses we will never run](#never-run)).

**Cadence.** Releases are monthly for the first year, then quarterly. Each is cumulative,
reviewed by a person, signed, and witnessed, and is never deleted or changed
([cadence](#cadence)). Tables update in batches: a table is updated only after at least five of
its reports have changed, so subtracting one release from the next shows at least five people's
answers mixed together, the same protection as a table cell ([why](#cadence)). The rules
themselves can change only by a versioned amendment announced a full release period in advance
([amendment](#amendment)).

## How we count reports {#how-we-count}

Every site that publishes a report count is asking you to take that number on faith. Ours is
checkable.

The moment a report is stored, it is also committed to a public, append-only log: a hash of the
report mixed with a secret random value, so the log reveals nothing about any report and no one —
including the person who submitted it — can find a particular entry. With every release we
publish the full list of log entries, the root that summarises them, and the previous release's
root. The release itself is signed, and its hash is recorded in two public transparency logs we
do not control.

That lets anyone check, without trusting us: that the published count is the number of entries
in the log; that nothing was removed, reordered, or backdated between releases; that the tables
were computed from that log under rules fixed before the data existed; and that a release has not
been quietly replaced since. Reports excluded from the tables for quality reasons are never
deleted: they stay in the log and are listed, by position and reason, in every release
([exclusions](#exclusions)).

We cannot independently verify report counts published elsewhere, and we do not claim they are
wrong. We can only say that ours is checkable — by you, with the steps below.

## What this does not prove {#not-proven}

- **That any report is true.** Nothing can. A fabricated report is committed as faithfully as an
  honest one. What is guaranteed is that whatever was committed was counted, and nothing was
  altered afterwards.
- **That reports came from different people.** Because no report is linked to a person, we
  cannot detect whether reports came from someone who previously submitted. This is an inherent
  downside to our privacy-first approach. What we can detect is a pattern: the
  coordinated-submission detector — a script in the public repository, `tools/detect.py` — flags
  reports that contradict themselves and unusual bursts, such as many reports about one compound
  arriving on one day. Flagged reports are left out of the tables and listed by log position in
  each release's exclusion list, and each release page ends with an **Integrity log** section
  (table T14 in the spec) showing how many were flagged, why, and a note on any pattern found.
- **That a report was not dropped before commitment.** The log proves what happened after a report
  entered it. The insertion policy is published: every submission that passes validation, the bot
  trap, and the hourly rate limit is committed, in the same transaction that stores it, with
  nothing held in between. A submission refused by the rate limit is shown an error and is not
  stored. You have to take that on the code, which is public, and on the operator.
- **That the published tables are the only computation that was run.** The specification lists
  every table that will ever be published. Anything else computed privately is, by definition,
  not published — and the specification cannot be extended without a witnessed amendment one
  release period in advance.

## Verify a release yourself {#verify}

You need Python 3 and the release directory; the two external witnesses need `openssl`,
`rekor-cli` and `ots`. One command runs every check — provided you hand it a copy of the signing
key that did not ship inside the release (the repository's `releases/pubkey.pem`, or a copy you
saved earlier), because a key inside the release proves nothing:

```
python3 tools/verify_release.py releases/2026-12 --prior releases/2026-11 \
    --spec spec/RELEASE_SPEC.md --taxonomy spec/taxonomy.v1.json --pubkey releases/pubkey.pem
```

`tools/verify_release.py` is in the public repository, is short, and reads nothing but the files
you give it. Each line of its output is one of the checks below.

### 1. The files are the files

`release.json` lists the SHA-256 of every other file in the release. Recompute any of them
(`sha256sum releases/2026-12/tables/T8.json`) and compare. If they match, that table is
byte-for-byte what was signed and witnessed.

### 2. The count is the count

`merkle/leaves.txt` is the full list of log entries at release time, one per line. The number of
lines is the committed count in `release.json` and in table T0; the Merkle root recomputed from
the lines equals the published root. The tree is the RFC 6962 construction — interior node =
SHA-256(0x01 ‖ left ‖ right), a lone right-hand node promoted — and `tools/pa_store.py` has it in
twenty lines.

### 3. Nothing was removed or backdated

The previous release's `leaves.txt` must be an exact prefix of this release's. If it is, every
report committed as of the previous release is still there, in the same position, and everything
since was appended after it. `release.json` records the previous release's root as `prior_root`,
so the chain can be followed back to the first release.

### 4. The rules were fixed first

`release.json` carries the SHA-256 of `spec/RELEASE_SPEC.md` and of `spec/taxonomy.v1.json` as
they stood when the release was computed. `spec/WITNESS.md` records the transparency-log entries
for those documents. If the hashes match, the tables were computed under rules that predate the
data.

### 5. Tables updated in batches

With `--prior`, the `updates` line checks that every table `release.json` lists as republished is
identical to the prior release's, and that every updated table names this release. The operator,
with the private store, can also have it re-run the batch decision on the store as it stood at
that release and confirm it comes out the same.

### 6. The release was witnessed

`witness/release.json.sig` is a detached signature on `release.json` under the key in
`witness/pubkey.pem`. The same key will be published at `/releases/pubkey.pem` and in the
repository before the first real release; until then there is no signing key and nothing to check.

```
openssl dgst -sha256 -verify /path/to/your/copy/of/pubkey.pem -signature witness/release.json.sig release.json
```

`witness/release.json.rekor.json` names the entry in the Sigstore Rekor public transparency log
holding that hash and signature — confirm it with `rekor-cli get --log-index <log_index>`.
`witness/release.json.ots` is an OpenTimestamps proof anchoring the hash in the Bitcoin
blockchain — confirm it with `ots verify -f release.json witness/release.json.ots`. Two
independent logs, neither operated by us, each showing the hash existed no later than the recorded
time. A release cannot later be quietly replaced: the replacement would not match the witnessed
hash.

### Checking what leaves your browser

Open your browser's network panel before pressing Continue on any screen of the report form. Each
request is a POST to `/contribute` whose body holds: `at` (which screen you are on), `go` (the
button you pressed), `s` (every answer so far, as a base64url-encoded JSON object of vocabulary
ids — decode it with any base64 tool), the choices you just made on that screen under their field
names, and an always-empty field named `website` — the invisible bot trap, which your browser
submits blank. Every value is a short id from the schema; none is anything you typed. There is no
cookie, no request to any other host, and no request at all until you press a button. Nothing is
stored on the server until the final *Agree and submit*.
