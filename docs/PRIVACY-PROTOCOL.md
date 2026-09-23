# Privacy protocol

Strong privacy encourages more reporting. We don't want to know who you are and take significant
steps to avoid doing that. This page details how.

Looking for the legal stuff instead? Read our [privacy statement and terms](/legal).

We want your questions and feedback. [Contact us](/contact).

## 1. What we promise {#promises}

- **We hold nothing that identifies a report.** The report form asks for no account, name,
  email, phone, cookie, key, receipt, or location; none is stored with a report; and your
  network address is never written down. There is nothing to link a report to a person, so
  nothing to leak, subpoena, or sell. (The contact page is separate: see §3.)
- **We ask only for rounded answers.** Every question on the report form is a fixed choice — a
  dose band, a duration bucket, a kind of source — so the record cannot carry the precision that
  matching it to a person would need. There is nowhere to type on the report form.
- **We store nothing until you say so.** The form holds your answers only in the page you are
  looking at. The server writes one row, at the moment you press *Agree and submit*, and never
  updates it.
- **We publish only aggregates, under rules fixed in advance.** Every table that will ever be
  published, and the threshold for each, is written down and will be witnessed in a public log
  before the first report is accepted. Small groups are suppressed. Individual reports are never
  shown to anyone — not to researchers, not to a buyer, not in a wind-down.
- **We will never try to work out who you are**, and we will never let anyone else use our data
  to.
- **The count is checkable.** Every accepted report is committed to a public log anyone can
  verify ([release spec](RELEASE-SPEC-SUMMARY.md)).
- **Nobody pays us and we pay nobody.**

What a careful design still cannot do is set out, without softening, in
[What we cannot promise](#cannot-promise) at the foot of this page.

## 2. What a report contains {#what-is-collected}

Fifteen multiple-choice answers: thirteen about one compound — which compound, route, dose
bands, frequency, kind of source, duration, whether it was tested, the main goal and what
happened, side effects from a fixed list with when they started and whether they stopped,
whether you are still taking it — and an optional age band and sex or gender. The
server adds the day it arrived (not the time) and a random secret value used only for the
public append-only log described in §7. That is the entire record. The complete field list and every allowed value
is the [schema](../spec/SCHEMA.md).

## 3. What is not collected, and what is not logged {#logging}

**What we never ask for.** No account, no email, no name, no phone, no date of birth, no cookie,
no key, no vendor or brand, no location of any granularity — not your country, not your state.
No free text: there is nowhere to type on the report form.

**The contact page** is the one place on the site where you can type. A message sent there is
stored on our server, forwarded to the operator's mailbox, and deleted within 30 days. It is kept
entirely separate from reports, and it is the reason we ask you never to describe a report you
submitted in a message.

**What leaves your browser.** The form never asks for the precise thing, only the rounded one: a
dose range instead of the milligram, a duration bucket instead of a start date, the kind of
source instead of the vendor. Nothing is sent until you press a button, and nothing is stored
until you press the last one.

**Your network address.** Over the public web address, the server reads your IP address once, to
limit how many submissions one connection can make in an hour: it hashes the address with a
random value that changes every hour, keeps the count in memory, and never writes any of it to
disk. After an hour it cannot be recovered even by us. Over the Tor onion service there is no
address at any layer. Nothing else about your connection is read.

**Your browser.** Every web server receives headers such as the browser's name and language.
Ours never reads or stores them, and there is no JavaScript on the site, so there is no way to
fingerprint a device — no canvas, fonts, screen, or hardware signals are ever examined.

**What this site loads.** Nothing from anyone but us — no analytics, no fonts, no CDN, no error
reporting, no CAPTCHA, no scripts. Your browser's network panel should show exactly one host. A
check that fails our build enforces it.

**Two ways in: the public web address and a Tor mirror.** The same site, the same code, the
same rules, at two addresses: `https://privateanecdata.org` and, in Tor Browser,
`http://unxzqdwshn2ftzivh3bg7e63mvn3ccsxs2d5oplxd7z3djs3qvppjhyd.onion`. On the public address, our hosting provider necessarily sees your
network address (§3 above), and your own network provider can see that you visited a site about
peptides. Through the Tor mirror neither can: no one on our side receives an address, and Tor
Browser also blocks the fingerprinting that ordinary browsers allow. We run the mirror for the
same reason major news organisations run theirs — so that reading and contributing do not require
telling anyone you did. It is listed openly here and in [Subprocessors](SUBPROCESSORS.md), and nothing exists on one
address that does not exist on the other.

**Location.** We do not ask for it, look it up, or log it. Today the server performs no
geographic lookup of any kind. If we ever enable a regional block on the public web address (to
decline connections from regions we do not serve), it would work by checking the region of an
address in memory to decide whether to serve the page, keeping nothing — and this paragraph
would change to say so before it was switched on. The onion service cannot be region-blocked.

**Logs.** The web server's access log is off. The application writes nothing per request. The
only logs that exist are process logs — startup, certificate renewal, errors — kept in memory and
expiring within a day. Two honest caveats. A failed TLS handshake is logged by the HTTP server with
the address that failed — a connection that never became a request. And when the web server
cannot reach the application (for example during a restart), it logs the error; our configuration
deletes the address, port, headers and path from that entry before it is written. Both logs are
volatile and expire within a day.

**The hosting provider.** To deliver a page, the provider's network necessarily carries your
packets and therefore your IP address. We do not control what its own network layer keeps; the
provider, its region, and its retention policy are named in [Subprocessors](SUBPROCESSORS.md),
which lists every party involved — there are three.

**Backups** are encrypted copies of the store and contain exactly what §2 describes. Retention
is stated in [Legal process](LEGAL-PROCESS.md).

## 4. How a report is kept from pointing at you {#de-identification}

- **Coarse by construction.** The form never asks for the exact dose, date, or place; it offers
  bands, buckets, and kinds. What is never asked cannot be recorded.
- **Nothing you type is stored.** Every control is a fixed choice, and the server re-checks each
  answer against the list it would have offered before writing anything. The one text box on the
  page is invisible, exists to catch automated submitters, and discards the submission if filled.
- **One goal, not many.** A combination of several goals was the single most identifying thing a
  report could carry, so the form asks for the main one.
- **No location, ever.** Not country, not state.
- **Small groups are never shown.** Any published cell under 5 reports is hidden, and one
  neighbouring cell is hidden with it so the small one cannot be recovered by subtraction; both
  are labelled "not shown", never with a number. A
  compound with fewer than 10 reports is not shown under its own name. Age and sex are reported
  only for all contributors together and are never crossed with anything.
- **Disclosure grows with numbers.** What is published about a compound depends on how many
  people have reported it — a count first, distributions later, outcomes-by-goal later still —
  so the number of published figures never gets close to the number of reports behind them.
- **We measure it.** How distinctive a single report is on several combinations of fields is
  computed on synthetic data in the [schema](../spec/SCHEMA.md), and re-computed on the real store
  before every release as a private check. We do not publish the real figures: exact numbers on
  combinations that include compound, age and sex would let someone who submits a few reports
  watch them move and learn about a report already there. We do not claim a rounded report can
  never be distinctive; see [what we can and cannot promise](WHAT-WE-CAN-AND-CANNOT-PROMISE.md).

## 5. The commitment {#no-reidentification}

We will not attempt to identify any person from any report, and we will not allow anyone else
to. We do not search the store for a particular person's report for any reason, including at that
person's request. Individual reports are never displayed, shared with researchers, licensed, sold,
or transferred, de-identified or otherwise, to anyone, including a buyer or trustee in a sale or
wind-down; if the project ends, the store is destroyed under the [shutdown protocol](SHUTDOWN.md).
The one thing we cannot refuse is valid legal process, which could compel production of the
store; [Legal process](LEGAL-PROCESS.md) says what that would and would not obtain — nothing in
the store identifies anyone.
The [terms](TERMS.md) §4 make this a promise to every contributor that binds any successor.

It follows that **we cannot find, correct, or delete your report after you submit it**: we hold
nothing that says which report is yours, and no way to check that a request about a report comes
from the person who made it. The form says so before you submit. If that is not acceptable, do
not submit.

## 6. What is published — the release specification {#release-specification}

Only aggregate statistics. Individual reports are never displayed, shared, licensed, or given to
researchers, in any form. The tables that can be published, and the number of reports each one
needs before it appears, are fixed in the [release specification](../spec/RELEASE_SPEC.md) — a
document that will be witnessed in a public transparency log before the first report is accepted,
and that can be changed only by a versioned amendment announced a full release period
in advance. Our code, schema, and rounding rules are public with it. In brief:

- **Tiers.** Under 10 reports, a compound is counted only inside its class. At 10: its count,
  route, and source. At 50: every one-way distribution — dose bands, frequency, duration, purity
  testing, effects, status, what people took it for. At 100: outcome by goal. At 200:
  percentages with intervals, and effect timing. At 1,000: the one cross-compound view, stratified
  and never pooled.
- **Floors.** Cells under 5 are hidden, with complementary suppression across every published
  total. A cross-tabulation stratum needs 20 reports. Percentages need 100 in the denominator.
- **Never.** No table crossing age or sex with anything; no three-field cross; no mean or average
  of any scale; no ranking or "most effective"; no comparison statistic between compounds; no
  per-vendor or per-region breakdown (no such fields exist); no row, partial row, or synthetic row;
  no live count; no statistic on request.
- **Cadence.** Cumulative snapshots, monthly for the twelve months after the first release and
  quarterly after, each
  reviewed by a person, signed, and witnessed. A release is never deleted or changed. Tables
  update in batches: new reports enter a table only in a batch of at least five, and excluded
  ones leave it the same way, so subtracting one release from the next shows at least five
  reports' answers mixed together, never fewer. Report counts are always current; a table
  waiting for its batch is shown unchanged and says which release computed it.

## 7. Counting honestly {#counting}

Our numbers are real. This section shows how anyone can check.

Every accepted report is committed, in the same transaction that stores it, to an append-only
log: a hash of the report with a secret per-report value, so the log reveals nothing about any
report and no one — not even the person who submitted it — can find a particular entry. With
every release we publish the whole list of log entries, the root that summarises them, and the
previous release's root. Anyone can recompute the root, confirm the count equals the number of
entries, and confirm the previous list is an exact prefix of this one — that nothing was removed,
reordered, or backdated between releases.

The release's manifest, which carries the hash of every published file, is signed and its hash is
submitted to two independent public logs we do not control — Sigstore Rekor and OpenTimestamps
(anchored in Bitcoin) — so a release cannot be quietly replaced later. Reports excluded for
quality reasons are never deleted: they stay in the log, are listed by position, reason and date
in every release, and leave the tables in batches of at least five. Each release page ends with an *Integrity log* section: how many
reports the coordinated-submission detector (public code: `tools/detect.py`) flagged, for what
reason, and a note on any pattern it found.

**What this does not prove:** that any report is true, that reports came from different people,
or that a submission was never dropped before it entered the log. The full procedure, what each
check proves, and what none of them can, is in [How we count reports](RELEASE-SPEC-SUMMARY.md#how-we-count).

## 8. Changes {#changes}

This protocol, the privacy statement, the terms, the schema, and the release specification are
versioned. Each version's hash is submitted to a public transparency log when it takes effect,
recorded in the witness record (`spec/WITNESS.md` in the repository), so a change cannot be quiet or backdated. A change
that reduces a promise does not apply to reports received before it — and since reports cannot be
separated by contributor, in practice it cannot apply to the store at all.
