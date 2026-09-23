# Release specification

**Version 1.0 — effective from the first release.** This document enumerates every statistic that will ever be
published from the submission store, and the rule that governs each one. It is fixed before the
first report is accepted, its hash is submitted to a public transparency log, and it is changed
only by a versioned amendment that is itself witnessed before it takes effect.

The purpose is that no one — including us — can decide *after* seeing the data which results to
show. What is listed here is published on schedule regardless of what it says. What is not listed
here is never published.

## Definitions

- **Report** — one row in the submission store, as defined in [SCHEMA.md](SCHEMA.md).
- **Release** — a set of static files generated from the store at a point in time, reviewed by a
  person, committed with a signed tag, and witnessed.
- **Cell** — one count in one published table.
- **Denominator** — the number of reports a proportion is computed over.
- **Class** — a mechanism class from SCHEMA.md. Classes are published as report counts only.
- **Unit** — anything published as one piece and computed from one set of reports: a compound's
  one-way tables; one row of a table split by status (stop reason), goal or side effect; or the
  all-reports tables (see *Cadence*).

## Thresholds and disclosure tiers {#tiers}

Thresholds are fixed. They are not tuned after data exists.

The set of tables published for a compound grows with that compound's report count, so that the
number of published cells stays near or below the number of rows they are computed from. This is
the control against reconstruction from aggregates: publishing roughly n or more accurate cells
about n rows lets an adversary solve for the rows, and a single unlock threshold with the full
table set would publish ~150 cells per compound at n=10.

| Tier | Compound n | What is published under the compound's name |
|---|---|---|
| **0** | under 10 | Nothing. The compound is counted in its class's report count only and is shown as "fewer than 10 reports." |
| **1** | 10–49 | Report count (T0). Route (T1) and source channel (T2) as counts. |
| **2** | 50–99 | All remaining one-way tables as counts: dose bands (T3), frequency (T4), duration (T5), purity (T6), adverse effects (T10), status and stop reason (T12), primary goal (T16). (T7, handling, was removed before the freeze and its number is not reused.) |
| **3** | 100–199 | Outcome by goal (T8), for any goal stratum with at least 20 reports. Still counts only. |
| **4** | 200–999 | Percentages with 95% intervals on every table above. Adverse-effect onset and dechallenge (T11). |
| **5** | 1,000+ | The compound participates in the cross-compound outcome view (T9) for any goal where at least one other compound is also at tier 4 or above. |

No table is computed for a class. A class's table beside its compounds' tables would publish, by
subtraction, the reports on its compounds below 10 — with no floor and no suppression — so a class
is published as its report count only (T0). Demographics (T13) are overall-only and appear once
total reports reach 200.

Within every tier, these cell rules apply:

| Name | Value | Governs |
|---|---|---|
| **Cell suppression floor** | 5 | Any cell with a count below 5 is hidden. Complementary suppression is applied so a suppressed cell cannot be recovered by subtraction from a published total; the complement is also hidden. Every hidden cell, floor or complement, carries the same label, "not shown" — never a number, and never a label that reveals which of the two is the small one — where "published total" means every marginal any table publishes: the table's own n, and any subtotal or stratum size another table shows (the stopped subtotal and its complement for T12; the goal stratum sizes T8 shows, which is why T8 shows a stratum's size only when T16 shows that goal). |
| **Proportion display** | tier 4, and 100 | A percentage is shown only when the compound is at tier 4 and the specific denominator is at least 100 — so a small goal stratum inside a large compound stays as counts. Every percentage carries a 95% (Wilson) interval and its denominator, rendered inside the figure. |
| **Cross-tabulation** | 20 per stratum, 5 per cell | A two-way table is published stratum by stratum: a stratum appears only when it has at least 20 reports, and is otherwise shown as "fewer than 20 reports." Within a published stratum the cell floor and complementary suppression apply exactly as in a one-way table, with the stratum size as the published total. |

Cells per row, by tier, for a typical compound: tier 1 publishes ~14 cells (mostly suppressed at
the low end); tier 2 ~70; tier 3 ~95; tier 4 ~140. At each tier's lower bound the ratio stays
near or below 1.

A suppression floor is not a privacy guarantee — an adversary who can submit crafted reports can
push a cell over any threshold. The floor is a readability convention and a first-line control.
The real controls are the tiering above, that the set of tables is bounded, that no interactive
querying exists, and that this specification cannot be extended on request.

## Cadence and epochs {#cadence}

- Releases are **cumulative snapshots**: each release computes every table from all reports
  received to date, minus the exclusion list — in batches, as set out below.
- Cadence is **monthly for the first twelve months after the first release, then quarterly**.
  Monthly releases are identified `YYYY-MM`, quarterly ones `YYYY-QN`. The move to quarterly is
  stated here in advance and is not an amendment. The cadence may lengthen but not shorten
  without amendment.
- A release is never deleted. A later release supersedes but does not remove an earlier one.
- The exclusion list (see below) grows only, and an exclusion's date never changes. An excluded
  report leaves each table under the same batch rule as new reports enter it (below). Until its
  batch it stays in the table, even if the table takes in new reports meanwhile. The counts in T0
  leave it out at once.
- **There is no real-time feed, no live counter finer than the last release, and no
  interactive query interface.** Published counts are as of the release date.

**Tables update in batches of at least five.** A table is computed from a set of reports. Once
published, new reports enter it only in a batch of at least five, and reports the detector has
excluded leave it only in a batch of at least five. The two are batched separately, because in the
difference between two releases they would otherwise separate by sign. A report excluded before it
entered a table never enters one. Until a batch is ready, the earlier version is republished
unchanged, marked with the release that computed it. A table that is split into rows by status,
goal or side effect applies this to each row on its own, drawing only on reports already in its
compound's tables. Report counts are always current.

*Why:* we only publish aggregate statistics ([privacy protocol](../docs/PRIVACY-PROTOCOL.md)).
Updating a table after one new report could reveal an individual report's answers.

*Tables never restart.* A table that stops being shown — a compound that exclusions take below
10, a row below 20 reports, a table whose compound drops below the tier it needs — keeps its set of
reports, which goes on changing only by batches; it returns only through them, never as a fresh
computation. A row of T8 or T11 that its parent table's suppression hid when it was computed
stays hidden until it is next updated, so a row republished from an earlier release never reveals
a count that release's suppression hid (a shown row whose compound changes tier is re-stamped
with the same reports, to gain or drop percentages). A compound's first tables are computed from
all of its reports when it reaches 10; before then its reports are in no compound's table, and,
like every report, only in the all-reports demographics (T13). A compound's tables are shown only
while both the reports they are computed from and its current count number at least 10.

*Why no class tables.* Two kinds of table contain other tables' reports: a row, inside its own
compound, and the all-reports demographics (T13), which contain every report. A row's field
(outcome, onset, stop reason) appears in no other table, and T13 publishes only fields no compound
table carries (age band, sex). So the only subtraction available is one version of a table from
another version of the same table, which is what the batches govern. A class table would add a
second: the class minus its compounds.

*Enforcement.* One module applies all of this (`tools/update_floor.py`). The sets of reports are
not stored: each release replays the rule over every earlier release, from the store as it stood
at each (the log up to that release's length, exclusions up to its date — which is why an
exclusion is never backdated or re-dated, and the pipeline refuses one that is). For every table
it shows, `release.json` records the release that computed it, that release's date and the tier its
tables were computed at — never a count, and nothing for a table it does not show — and it lists
every earlier release. Before computing a release, the pipeline replays the prior release and
refuses to go on unless it comes out exactly as published, and it refuses a changed taxonomy
(changing the taxonomy would need an amendment and a changeover, not yet defined).
`tools/verify_release.py` checks that each shown table has a record at a tier that allows it,
names the release that computed it and carries the matching mark; that a table republished from
an earlier release is identical to the prior release's, and so is its figure where it has one of
its own, when the prior release also showed it; that exclusions only grow and never change; and,
given the store, replays the rule over the whole history and rebuilds every file, which must come
out byte for byte the same. That each update was a batch of at least five, and that the tables were
computed from the stored reports, are checkable only that way: the public files do not show it.

What this delivers: subtracting one release from the next shows, per table, the answers of at
least five reports that entered together, or of at least five that left together, never fewer.
Report counts move by any number; a bare count identifies no one. It does not stop a person who
submits four reports of their own, in the same month as someone else's, from knowing four of the
five; no batch size can (see *Thresholds*).

## Exclusions {#exclusions}

Reports flagged by the quality detector (malformed values, implausible combinations, coordinated
submission patterns) are **not deleted**. They remain in the Merkle-committed submission log. They
are listed, by log position, reason code and the date the exclusion was noted, in a separately
published exclusion list (`exclusions.json`), and they leave the tables in batches (see *Cadence*). The exclusion
list is itself part of each release. Exclusions are proposed by `tools/detect.py` and applied by a
person; the detector's rules are in that file.

Reason codes: `malformed` · `implausible` · `duplicate-pattern` · `coordinated` · `test`.

The published submission count is always the count of **all** committed reports; the excluded
count is shown beside it.

## The tables {#tables}

Every table below is computed per compound, for **each compound at or above the unlock
threshold**. No table is computed for a class. A compound below the unlock threshold is counted in
its class's report count and has no table of its own; like every report, its reports are in the
all-reports demographics (T13).

### T0 — Counts {#t0}

| Field | Rule |
|---|---|
| Total reports committed | Always published, with the Merkle root and log index |
| Reports excluded, by reason code | Always published |
| Reports per class | Published for every class with at least 5 reports; below that, "fewer than 5 reports." |
| Reports per compound | Published for compounds at or above unlock; below unlock, shown as "fewer than 10." This is a presentation rule, not a suppression rule: class totals are exact, so a single hidden compound's count within a class is inferable by subtraction. A bare count of reports on a compound identifies no one; complementary suppression protects cells within tables, not the T0 hierarchy. |
| Reports received since the prior release | Published, as the difference between the two committed counts. (Committed counts are exact — they are what the Merkle root commits to — so this difference is exact by construction.) |
| Tables as of | For each compound whose tables are republished unchanged, the release that computed them and the number of reports they were computed from (the same n the tables show). |
| Tables pending | A compound whose count is 10 or more while its tables are not shown, because exclusions took the reports they are computed from below 10 and no batch has brought them back: count only. |

### T1 — Route

Per compound: distribution of `route`. Counts from the tier at which the table unlocks; percentages at tier 4.

### T2 — Source channel

Per compound: distribution of `source_channel`. Counts from the tier at which the table unlocks; percentages at tier 4.

### T3 — Dose bands

Per compound: distribution of `start_dose` and, separately, of `current_dose`. Counts from the tier at which the table unlocks;
percentages at tier 4.

### T4 — Frequency

Per compound: distribution of `frequency` (which includes cycling). Counts from the tier at which the table unlocks;
percentages at tier 4.

### T5 — Duration

Per compound: distribution of `duration`. Counts from the tier at which the table unlocks; percentages at tier 4.

### T6 — Purity testing

Per compound: distribution of `purity_tested`. Counts from the tier at which the table unlocks; percentages at tier 4.

### T7 — (removed)

Handling/reconstitution was dropped from the schema before the freeze to shorten the form. The
number is retained so table ids stay stable.

### T8 — Outcome by goal {#t8}

**Per compound × goal:** distribution of `outcome` (no change / slight /
moderate / large) among reports that selected that goal. **Tier 3 and above.** Cross-tabulation rules apply: each
compound–goal stratum needs ≥20 reports, each cell ≥5. Percentages at tier 4. "Other (not listed)"
is counted as a goal but is never a stratum: there is no stated goal to condition on. A stratum's
size is shown only if T16 shows that goal's count; a goal T16 hides (below the floor, or the
complement protecting one that is) is shown here as "not shown", whatever its size, because its
size would give the hidden count away by subtraction from the compound total.

This is the efficacy instrument. It is presented as "of N people who took X hoping for Y, this
many reported no change / slight / moderate / large." It is never presented as an effectiveness
score, a rating, or a rate.

### T9 — Outcome by goal, across compounds {#t9}

**Per goal:** the T8 rows of every compound at tier 4 or above that has a publishable stratum for
that goal, side by side, **stratified by compound and never pooled**. The table for a goal is
published only when at least two compounds qualify and at least one of them is at tier 5. Every
number in it is already public in T8; the table adds juxtaposition, nothing else.

**Tier 5.** This is the only cross-compound view that will ever exist. It permits a reader to see that 40% of
BPC-157 reports for tendon injury reported no change while 55% of TB-500 reports did, with the
denominators beside each. It does not permit a ranking, a difference, a ratio, or a "better than"
statement, and the page will not compute one.

### T10 — Adverse effects

Per compound: for each adverse effect in the universal list and that compound's list, the number
of reports that selected it, over the compound's total reports, plus one cell for reports that
selected no effect at all. Cell floor 5. Percentages at tier 4. Effects below the cell floor are
shown as "not shown." Effects are multi-select, so cells do not sum to the total and no
complementary suppression is needed.

### T11 — Adverse effect onset and dechallenge

Per compound × adverse effect (only for effects at or above the cell floor in T10):
distribution of `onset`; distribution of `dechallenge`. **Tier 4 and above.** Cross-tabulation rules apply.

### T12 — Status and discontinuation

Per compound: distribution of `status`; among stopped reports, distribution of `stop_reason`.
The stopped reports are a stratum (≥20, else "fewer than 20"), and their subtotal — and therefore
its complement, the not-stopped subtotal — is a published total for complementary suppression in
the status table: neither partition may end with exactly one hidden cell. Counts from tier 2; percentages at tier 4.

### T13 — Demographics

**Overall only, never per compound:** distribution of `age_band`; distribution of `sex`;
the proportion of reports that declined each. Published once per release.

Age and sex are never crossed with compound, goal, dose, or any other field. They exist to
describe the contributor population as a whole and for no other purpose.

### T14 — Integrity log

Per release: the number of reports flagged by each detector rule in the period, and a plain-
language description of any coordinated-submission pattern detected, without any information that
would identify the pattern's rows. This is the running integrity log.

### T16 — Primary goal

Per compound: distribution of `goal` — what people took it for — over the compound's predefined
goal list plus "other (not listed)". Counts from tier 2; percentages at tier 4. This is the single
source of exact goal counts: T8 shows a row's size only for a goal shown here now and shown here
when the row was computed, and that size can differ from the count here by reports still waiting
for the row's next batch. When a complement must be hidden here, a goal with
fewer than 20 reports (which T8 would not size exactly anyway) is preferred.

### T15 — (removed)

The uniqueness summary was removed before the first release. Exact uniqueness percentages on
fields that include compound, age band and sex let someone who submits a few reports of their own
watch the figures move and learn whether an existing report falls in a given combination. The
operator runs `tools/uniqueness.py real` on the store before every release, privately, as a gate;
the figures are not published. The number is retained so table ids stay stable.

## What is never published {#never}

- Any table not listed above.
- Any table crossing three or more fields.
- Any table crossing `age_band` or `sex` with any other field.
- Any table for a compound below the unlock threshold under its own name.
- Any table for a class. (Classes are published as counts.)
- Any mean, average, or sum of an ordinal scale. Distributions only.
- Any ranking, league table, "top rated," "most effective," or ordering of compounds by outcome.
- Any difference, ratio, or comparison statistic between two compounds.
- Any per-vendor, per-pharmacy, or per-brand breakdown. (No such field exists.)
- Any per-region breakdown. (No such field exists.)
- Any row, any partial row, any synthetic row, any row-shaped artifact.
- Any count finer than the last release, on any page, including a live counter.
- Any statistic in response to a request. Requests are answered by pointing at this document.

## Presentation rules {#presentation}

These apply to every rendered figure and table:

1. The denominator is rendered inside every figure, in the same image, not in surrounding text.
2. Every percentage carries a 95% interval, rendered inside the figure.
3. Every figure carries, inside the image, the sentence: *"Self-reported. Not evidence of
   effectiveness or safety. See methodology."*
4. Suppressed cells are shown as "not shown," never blank, never zero, and never with a label that
   distinguishes a floor suppression from its complement.
5. Compounds below unlock are shown as "fewer than 10 reports — not enough to show," never hidden.
6. No figure orders compounds by any outcome. Compounds appear in the fixed order of SCHEMA.md.
7. Robust statistics only where a summary is unavoidable: medians and interquartile ranges, never
   means.

## Release procedure {#procedure}

1. The pipeline runs against the store and the current exclusion list. It is run by a person,
   by hand, on the host (the exact commands are in `deploy/README.md`), never on a schedule.
2. It writes static files: one JSON per table, one rendered figure per table, the exclusion list,
   the integrity log, the full list of Merkle leaves in log order (`merkle/leaves.txt`, so that
   anyone can recompute the root and the count), and `release.json` carrying the release date,
   the schema version, this document's version and hash, the Merkle root and leaf count, the
   prior release's root, and the SHA-256 of every file. The pipeline first verifies the store
   against its own log and refuses to run if any row fails; it then audits its own output and
   refuses to write any count below the cell floor.
3. A person reviews the output against this specification before anything is published.
4. The files are committed under a signed tag `release/<id>` (`YYYY-MM` while monthly, `YYYY-QN` once quarterly).
5. `release.json` is signed; its hash is submitted to the Sigstore Rekor public-good instance and
   timestamped with OpenTimestamps; the signature, public key, Rekor log index and entry UUID, and
   the upgraded `.ots` file are published alongside in `witness/`. `release.json` itself is never
   modified after signing.
6. The release goes live. Nothing about a prior release changes. Anyone can check the published
   files, the log and its chain to the prior release, the specification's hash and the witnesses
   with `tools/verify_release.py`; that the pipeline ran against the store and that a person
   reviewed the output cannot be checked from outside (see
   [How we count reports](../docs/RELEASE-SPEC-SUMMARY.md#how-we-count)).

## Amendment {#amendment}

This specification may be amended only by:

1. Publishing the proposed amendment, with a version increment, at least one full release period
   before it takes effect.
2. Submitting the amended document's hash to the transparency log on publication.
3. Applying the amendment only to releases computed after the effective date.

An amendment may tighten a threshold or remove a table without notice. An amendment that loosens
a threshold or adds a table requires the full period.

## Witness {#witness}

This document's SHA-256 and its transparency-log entry are recorded in `spec/WITNESS.md` when it
is witnessed, before the first release; that file lists every witnessed version.
