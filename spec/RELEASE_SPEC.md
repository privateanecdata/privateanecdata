# Release specification

**Version 0.1 — draft, pre-launch.** This document enumerates every statistic that will ever be
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
- **Class** — a mechanism class from SCHEMA.md, used to roll up compounds below threshold.

## Thresholds and disclosure tiers

Thresholds are fixed. They are not tuned after data exists.

The set of tables published for a compound grows with that compound's report count, so that the
number of published cells stays near or below the number of rows they are computed from. This is
the control against reconstruction from aggregates: publishing roughly n or more accurate cells
about n rows lets an adversary solve for the rows, and a single unlock threshold with the full
table set would publish ~150 cells per compound at n=10.

| Tier | Compound n | What is published under the compound's name |
|---|---|---|
| **0** | under 10 | Nothing. The compound contributes to its class tables only and is shown as "fewer than 10 reports." |
| **1** | 10–49 | Report count (T0). Route (T1) and source channel (T2) as counts. |
| **2** | 50–99 | All remaining one-way tables as counts: dose bands (T3), frequency and titration (T4), duration (T5), purity (T6), handling (T7), adverse effects (T10), status and stop reason (T12), primary goal (T16). |
| **3** | 100–199 | Outcome by goal (T8), for any goal stratum with at least 20 reports. Still counts only. |
| **4** | 200–999 | Percentages with 95% intervals on every table above. Adverse-effect onset and dechallenge (T11). |
| **5** | 1,000+ | The compound participates in the cross-compound outcome view (T9) for any goal where at least one other compound is also at tier 4 or above. |

Class tables follow the same tiers using the class's report count. Demographics (T13) are
overall-only and appear once total reports reach 200.

Within every tier, these cell rules apply:

| Name | Value | Governs |
|---|---|---|
| **Cell suppression floor** | 5 | Any cell with a count below 5 is shown as "fewer than 5." Complementary suppression is applied so a suppressed cell cannot be recovered by subtraction from a published total. |
| **Proportion display** | tier 4, and 100 | A percentage is shown only when the compound (or class) is at tier 4 and the specific denominator is at least 100 — so a small goal stratum inside a large compound stays as counts. Every percentage carries a 95% (Wilson) interval and its denominator, rendered inside the figure. |
| **Cross-tabulation** | 20 per stratum, 5 per cell | A two-way table is published stratum by stratum: a stratum appears only when it has at least 20 reports, and is otherwise shown as "fewer than 20 reports." Within a published stratum the cell floor and complementary suppression apply exactly as in a one-way table, with the stratum size as the published total. |

Cells per row, by tier, for a typical compound: tier 1 publishes ~14 cells (mostly suppressed at
the low end); tier 2 ~85; tier 3 ~110; tier 4 ~155. At each tier's lower bound the ratio stays
near or below 1.

A suppression floor is not a privacy guarantee — an adversary who can submit crafted reports can
push a cell over any threshold. The floor is a readability convention and a first-line control.
The real controls are the tiering above, that the set of tables is bounded, that no interactive
querying exists, and that this specification cannot be extended on request.

## Cadence and epochs

- Releases are **cumulative snapshots**: each release recomputes every table from all reports
  received to date, minus the exclusion list.
- Initial cadence is **quarterly**. The cadence may lengthen but not shorten without amendment.
- A release is never deleted. A later release supersedes but does not remove an earlier one.
- The exclusion list (see below) is applied identically to every table in a release, and the same
  exclusion list is used for every release computed on or after the date it was published.
- **There is no real-time feed, no live counter finer than the last release, and no
  interactive query interface.** Published counts are as of the release date.

Two releases can be differenced by anyone. Cumulative snapshots at quarterly intervals with a
suppression floor of 5 mean that the difference between two releases reveals, at most, the
distribution of reports received in one quarter, subject to the same floor. This is a stated
limit, not a solved problem; the bounded table set is what keeps it bounded.

## Exclusions

Reports flagged by the quality detector (malformed values, implausible combinations, coordinated
submission patterns) are **not deleted**. They remain in the Merkle-committed submission log. They
are listed, by log position, reason code and the date the exclusion was noted, in a separately
published exclusion list (`exclusions.json`), and they are omitted from every table. The exclusion
list is itself part of each release. Exclusions are proposed by `tools/detect.py` and applied by a
person; the detector's rules are in that file.

Reason codes: `malformed` · `implausible` · `duplicate-pattern` · `coordinated` · `test`.

The published submission count is always the count of **all** committed reports; the excluded
count is shown beside it.

## The tables

Every table below is computed for **each compound at or above the compound unlock threshold**
and for **each class**. "Per compound" below means "per compound or class." A compound below the
unlock threshold contributes to its class's tables and to no compound-level table.

### T0 — Counts

| Field | Rule |
|---|---|
| Total reports committed | Always published, with the Merkle root and log index |
| Reports excluded, by reason code | Always published |
| Reports per class | Published for every class |
| Reports per compound | Published for compounds at or above unlock; below unlock, shown as "fewer than 10." This is a presentation rule, not a suppression rule: class totals are exact, so a single hidden compound's count within a class is inferable by subtraction. A bare count of reports on a compound identifies no one; complementary suppression protects cells within tables, not the T0 hierarchy. |
| Reports received since the prior release | Published, as the difference between the two committed counts. (Committed counts are exact — they are what the Merkle root commits to — so this difference is exact by construction.) |

### T1 — Route

Per compound: distribution of `route`. Counts from the tier at which the table unlocks; percentages at tier 4.

### T2 — Source channel

Per compound: distribution of `source_channel`. Counts from the tier at which the table unlocks; percentages at tier 4.

### T3 — Dose bands

Per compound: distribution of `start_dose` and, separately, of `current_dose`. Counts from the tier at which the table unlocks;
percentages at tier 4. **Never published for a class** — dose bands are compound-specific and a
class rollup would be meaningless.

### T4 — Frequency and titration

Per compound: distribution of `frequency`; distribution of `titration`. Counts from the tier at which the table unlocks;
percentages at tier 4.

### T5 — Duration

Per compound: distribution of `duration`. Counts from the tier at which the table unlocks; percentages at tier 4.

### T6 — Purity testing

Per compound: distribution of `purity_tested`. Counts from the tier at which the table unlocks; percentages at tier 4. Additionally,
per class and overall: the same distribution.

### T7 — Handling

Per compound: distribution of `reconstitution`. Counts from the tier at which the table unlocks; percentages at tier 4.

### T8 — Outcome by goal

**Per compound × goal:** distribution of `outcome` (no change / slight / moderate / large) among
reports that selected that goal. **Tier 3 and above.** Cross-tabulation rules apply: each
compound–goal stratum needs ≥20 reports, each cell ≥5. Percentages at tier 4. "Other (not listed)"
is counted as a goal but is never a stratum: there is no stated goal to condition on.

This is the efficacy instrument. It is presented as "of N people who took X hoping for Y, this
many reported no change / slight / moderate / large." It is never presented as an effectiveness
score, a rating, or a rate.

### T9 — Outcome by goal, across compounds

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
shown as "fewer than 5." Effects are multi-select, so cells do not sum to the total and no
complementary suppression is needed.

### T11 — Adverse effect onset and dechallenge

Per compound × adverse effect (only for effects at or above the cell floor in T10): distribution
of `onset`; distribution of `dechallenge`. **Tier 4 and above.** Cross-tabulation rules apply.

### T12 — Status and discontinuation

Per compound: distribution of `status`; among stopped reports, distribution of `stop_reason`.
The stopped reports are a stratum (≥20, else "fewer than 20"), and their subtotal is a published
total for complementary suppression in the status table. Counts from tier 2; percentages at tier 4.

### T13 — Demographics

**Overall only, never per compound or class:** distribution of `age_band`; distribution of `sex`;
the proportion of reports that declined each. Published once per release.

Age and sex are never crossed with compound, goal, dose, or any other field. They exist to
describe the contributor population as a whole and for no other purpose.

### T14 — Integrity log

Per release: the number of reports flagged by each detector rule in the period, and a plain-
language description of any coordinated-submission pattern detected, without any information that
would identify the pattern's rows. This is the running integrity log.

### T16 — Primary goal

Per compound: distribution of `goal` — what people took it for — over the compound's predefined
goal list plus "other (not listed)". Counts from tier 2; percentages at tier 4. This is the
denominator table for T8: the stratum sizes T8 publishes at tier 3 are these same counts.

### T15 — Uniqueness summary

Per release: the summary numbers from `tools/uniqueness.py real` run on the store at release time
— the same five quasi-identifier sets as in SCHEMA.md, with percent unique and median cell size.
Never any row-level output.

## What is never published

- Any table not listed above.
- Any table crossing three or more fields.
- Any table crossing `age_band` or `sex` with any other field.
- Any table for a compound below the unlock threshold under its own name.
- Any dose-band table for a class.
- Any mean, average, or sum of an ordinal scale. Distributions only.
- Any ranking, league table, "top rated," "most effective," or ordering of compounds by outcome.
- Any difference, ratio, or comparison statistic between two compounds.
- Any per-vendor, per-pharmacy, or per-brand breakdown. (No such field exists.)
- Any per-region breakdown. (No such field exists.)
- Any row, any partial row, any synthetic row, any row-shaped artifact.
- Any count finer than the last release, on any page, including a live counter.
- Any statistic in response to a request. Requests are answered by pointing at this document.

## Presentation rules

These apply to every rendered figure and table:

1. The denominator is rendered inside every figure, in the same image, not in surrounding text.
2. Every percentage carries a 95% interval, rendered inside the figure.
3. Every figure carries, inside the image, the sentence: *"Self-reported. Not evidence of
   effectiveness or safety. See methodology."*
4. Suppressed cells are shown as "fewer than 5," never blank, never zero.
5. Compounds below unlock are shown as "fewer than 10 reports — not enough to show," never hidden.
6. No figure orders compounds by any outcome. Compounds appear in the fixed order of SCHEMA.md.
7. Robust statistics only where a summary is unavoidable: medians and interquartile ranges, never
   means.

## Release procedure

1. The pipeline runs against the store and the current exclusion list. It is triggered by a
   person (`workflow_dispatch`), never by a schedule.
2. It writes static files: one JSON per table, one rendered figure per table, the exclusion list,
   the integrity log, the full list of Merkle leaves in log order (`merkle/leaves.txt`, so that
   anyone can recompute the root and the count), and `release.json` carrying the release date,
   the schema version, this document's version and hash, the Merkle root and leaf count, the
   prior release's root, and the SHA-256 of every file. The pipeline first verifies the store
   against its own log and refuses to run if any row fails; it then audits its own output and
   refuses to write any count below the cell floor.
3. A person reviews the output against this specification before anything is published.
4. The files are committed under a signed tag `release/YYYY-QN`.
5. `release.json` is signed; its hash is submitted to the Sigstore Rekor public-good instance and
   timestamped with OpenTimestamps; the signature, public key, Rekor log index and entry UUID, and
   the upgraded `.ots` file are published alongside in `witness/`. `release.json` itself is never
   modified after signing.
6. The release goes live. Nothing about a prior release changes. Anyone can check every step
   with `tools/verify_release.py`; see [How to verify](../docs/HOW-TO-VERIFY.md).

## Amendment

This specification may be amended only by:

1. Publishing the proposed amendment, with a version increment, at least one full release period
   before it takes effect.
2. Submitting the amended document's hash to the transparency log on publication.
3. Applying the amendment only to releases computed after the effective date.

An amendment may tighten a threshold or remove a table without notice. An amendment that loosens
a threshold or adds a table requires the full period.

## Witness

This document's SHA-256 and its transparency-log entry are recorded in `spec/WITNESS.md` at the
time of freezing. Until that file exists, this document is a draft.
