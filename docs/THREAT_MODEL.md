# Threat model

**Version 1.0.** This document is written as a specification: it states what
the system enforces, not what it worries about. Every mitigation listed here is either implemented
in code, enforced in CI, or stated as a published operating commitment. Where a risk cannot be
removed, that is stated in [What we can and cannot promise](WHAT-WE-CAN-AND-CANNOT-PROMISE.md).

## What this system is

A public website that accepts one-time, structured, identifier-free reports about peptide use,
from any source, and publishes aggregate statistics computed from those reports under a release
specification fixed before any data was collected.

## Assets

In priority order:

1. **The contributor's identity** — never collected, so never held.
2. **The association between a report and a person** — the only thing that could convert a
   report about drug use into a fact about a specific human. The design's purpose is
   to make this association unavailable to us and to anyone who obtains what we hold.
3. **The report's content** — coarsened structured fields about compound, source, dose, duration,
   outcomes and adverse effects. Sensitive in aggregate for the population; identifying only in
   combination with (2).
4. **The integrity of the published aggregates** — the product. Compromised by fabricated
   submissions, silent editing, or selective publication.
5. **The contributor's trust** — damaged by any gap between what we say and what the deployed
   system does.

## Adversaries

We design against, in decreasing order of concern:

- **A motivated individual with public information about a target** — a partner, employer,
  competitor, or anti-doping investigator who knows a specific person uses these compounds and
  wants to find their report. Has: public posts by the target, the published aggregates, the
  published source code, and the ability to submit crafted reports. Does not have: our database.
- **Legal process** — a subpoena, preservation demand, or warrant served on us or our host. Has:
  everything we hold. This adversary is the reason the design holds nothing that resolves to a
  person.
- **A compromised host or database** — an attacker who obtains the raw store. Same capability as
  legal process, without the notice.
- **A vendor or other party with a commercial interest in the published numbers** — submits
  fabricated reports to move a statistic. Has: the ability to submit at scale through any path we
  offer.
- **Ourselves** — a future operator, an acquirer, a bankruptcy trustee, or a version of the
  current operator under pressure. The design limits what any operator *can* do, not just what
  this one intends to.

We explicitly do not design against a nation-state adversary with the ability to compromise
endpoints, and we do not claim protection against an adversary who has compromised the
contributor's own device.

## What the server receives

One HTTP POST per screen of the form, each carrying the answers so far in a hidden field so the
server can render the next screen — and nothing is kept from any of them. Only the final POST, at
the moment the contributor confirms, is written, and it contains only fields drawn from the
frozen controlled vocabularies in [SCHEMA.md](../spec/SCHEMA.md), re-validated against them
immediately before the write. Specifically:

| Field | Form |
|---|---|
| Compound | One of a frozen list; rare entries are published only as part of a mechanism class's report count |
| Primary goal | One of that compound's predefined goal list |
| Source channel | One of eight channel types (including "don't know" and "other"); never a vendor, pharmacy, or brand name |
| Starting and current dose | A band, never a number |
| Frequency, duration | Buckets |
| Purity testing | One of five: did not test / tested, matched label / tested, did not match / tested, unsure how to read the result / don't know |
| Outcome for the stated goal | No change / slight / moderate / large |
| Adverse effects | Multi-select from a fixed list, each with an onset bucket and whether it resolved on stopping |
| Status | Still taking, finished a planned course, or stopped early — and if stopped, the main reason from a fixed list |
| Age band, sex or gender | Optional; six bands and five options |

**Not received, by construction:** name, email, phone, account, cookie, contribution key, IP
address (see *Network*), free text of any kind, exact dose, exact dates, start date or quarter,
vendor or pharmacy name, price, location at any granularity, device identifiers, or any field not
listed in the schema.

Coarsening is a property of the questions, not a transformation: the form never asks for the
exact value, so the server never receives one to round. Every control is a fixed choice — a dose
band, a duration bucket, a kind of source. The form runs no script at all, so there is no
client-side step to audit; the choices on the page are the only values that can be sent.

## What the server stores

Exactly the fields above, plus a day-granularity received date assigned on write, a per-row
secret salt, and the row's Merkle leaf in an append-only log table. The leaf is a hash of the salt
and the row, so anyone holding the store can recompute which log position belongs to which row;
the salt only prevents that matching from the published leaf list. Nothing else. There is no session table, no
draft table, no request log that references submissions, and no column that could hold an
identifier.

**Nothing is stored until the contributor confirms.** Multi-step form state is carried in the
request and rendered back to the contributor for review. Abandoned forms leave no record.

Every stored row is appended, with a per-row secret salt, to a Merkle log whose root is published
periodically (see *Integrity*). Rows are never updated. Rows excluded for quality reasons are
recorded in a separate, separately-published exclusion list with reason codes and the date each was
noted; they are not deleted from the log, and they leave the published tables only in batches of at
least five.

## What is published

Only the outputs enumerated in [RELEASE_SPEC.md](../spec/RELEASE_SPEC.md), which is fixed and
to be witnessed in a public transparency log before the first report is accepted. Each release is a
set of static files generated by a pipeline whose code is public, reviewed by a person before
publication, and committed with a signed tag.

The specification lists every table that will ever be published and the rule for every cell. No
table is added in response to a request. No interactive query interface exists. No row is ever
published, licensed, shared with a researcher, or otherwise disclosed, in any form, de-identified
or otherwise.

## Enforced mitigations, by threat

### Direct identification

*Threat:* a name, email, or contact detail arrives with a report.

*Enforced:* no such field exists in the schema, and nothing typed on the report form is ever
stored. Every control on the report form is a fixed choice, with one exception: a visually hidden text input that only an
automated submitter would fill, whose value is used solely to reject the submission and is never
written anywhere. Before the final write the server re-validates every field of the report
against the vocabulary the form would have offered, and rejects anything else — a tampered
request cannot store a value the form does not list. A check that runs in CI
(`tools/check_form.py`) renders every screen and fails if any control is not a schema field, a
routing field, or that one bot trap. The contact page is the only other form on the site; it is a
separate store, holds free text by design, is never joined to reports, and is pruned at 30 days.

### Linkage via public posts

*Threat:* a contributor posts publicly ("35M, started BPC-157 at 250 mcg in March for a tendon")
and an adversary matches that post to a stored row.

*Enforced:* the row does not contain the values a post contains. It contains a dose *band* rather
than 250 mcg, a duration bucket rather than a start date, a source *type* rather than a vendor. No
location is held at any granularity. Only one goal is held. The adversary must first obtain the
raw store (see *Legal process* and *Compromise*), then guess which bucket each of the target's
values fell in.

*Stated limit:* on the coarsened row, a determined adversary who holds the raw store and knows a
target's compound, age band, sex, goal, and dose band will find a small number of candidate rows
at any dataset size below tens of thousands. The schema publishes the uniqueness analysis that
quantifies this on synthetic data; the operator re-runs it on the real store before every release
and does not publish the real figures, which would themselves be a probe. This is why the raw
store is never published and why we hold nothing else.

### Timing correlation

*Threat:* a submission timestamp is matched to a public post timestamp.

*Enforced:* no timestamp finer than a day is written to any durable store. A report is committed
at the moment of confirmation, so the log preserves the exact order of commitment, and anyone who
holds the store can recover that order for every row (the salt is on the row); what they cannot
recover is a time finer than the day the received date gives. The published leaf list is in log
order, but a leaf cannot be matched to a report without that report's secret salt, which is never
published, so nothing public places any report in the sequence. Row IDs are random. No real-time
feed exists; counts are published only with releases.

### Network metadata

*Threat:* the contributor's IP address, TLS fingerprint, or user agent is recorded alongside the
submission.

*Enforced:* access logging is disabled at every layer we control — web server, reverse proxy, TLS
termination, and application. There is no CDN, WAF, or third-party edge in front of the origin. TLS
session-ticket keys are held in memory only and rotated automatically by the server; nothing about
a session is written to disk. Process logs (startup, certificate renewal, errors) are kept in
memory and expire within a day; an address can reach them in two ways: a failed TLS handshake is logged with the address that
failed (a connection that never became a request), and a handler error such as a 502 during a
restart is logged with the request's address, headers and path deleted by configuration. `Referrer-Policy: same-origin` is set (so no referrer ever leaves the
origin) and query parameters are rejected on the intake route. A Tor onion service provides a
second path with no IP for us to receive. The hosting provider necessarily receives the
IP to deliver the page; we publish the provider's name, region, and its own retention policy in
[SUBPROCESSORS.md](SUBPROCESSORS.md).

*Stated limit:* we cannot promise our host has never seen an IP. We can promise we do not log it,
do not store it, and have configured every layer under our control not to.

### Third-party disclosure

*Threat:* a script, font, image, or error report sends a request to a third party from a page
carrying health information.

*Enforced:* zero external origins. The Content-Security-Policy permits no external source of any
kind. CI fails the build if any resource references an external origin. No analytics, no CAPTCHA
service, no error-reporting SDK, no CDN-hosted library, no hosted fonts. This applies to every page
on the origin, not only the form.

### Draft and partial-submission leakage

*Threat:* the server records what a contributor typed and then changed, or a form they abandoned.

*Enforced:* no server-side draft store. No per-field validation endpoint. No per-keystroke or
per-blur requests. Nothing is persisted until the contributor confirms on the review screen.

### Database compromise and legal process

*Threat:* an attacker or a court obtains everything we hold.

*Enforced:* what we hold is the coarsened rows described above and nothing else. There is no
identifier column, no key table, no log that references a submission. The honest description of
what a subpoena would produce is: a set of rows with no field that resolves to a person, and no
auxiliary data with which to attempt it. Our handling of legal process is stated in
[LEGAL-PROCESS.md](LEGAL-PROCESS.md).

*Stated limit:* see *Linkage via public posts*. A party who obtains the store and independently
holds a target's public statements has a bounded but nonzero ability to shortlist rows.

### Small-cell disclosure and differencing

*Threat:* a published statistic reveals information about a small group, or the difference between
two releases reveals a single report.

*Enforced:* the release specification fixes a minimum cell size below which no value is published
and a display threshold below which no proportion is shown. Rare compounds are published only as
part of their mechanism class's report count; no table is computed for a class, because a class
table beside its compounds' tables would publish the small compounds' answers by subtraction. No
table is cross-tabulated on a rare compound. Releases are cumulative snapshots, and tables update
in batches: a table, or one row of a table split by status, goal or effect, takes in new reports
only in a batch of at least five and lets excluded reports go only in a batch of at least five,
batched separately, and is otherwise republished unchanged — so subtracting one release from the
next shows the answers of at least five reports that entered or left together. A report excluded
before it entered a table never enters one. A table that stops being shown keeps its set of reports
and returns only through batches, never as a fresh computation. The total number of distinct tables
that will ever be published is bounded by the specification.

*Stated limit:* a suppression threshold is not a privacy guarantee. An adversary who can submit
crafted reports can push a target's cell over any threshold. This is why the number of tables is
bounded, why no interactive querying exists, and why the specification cannot be extended on
request.

### Fabricated submissions

*Threat:* one party submits many reports to move a published number.

*Enforced:* a honeypot field that automated submitters fill and people cannot see; in-memory
rate limiting keyed on a salted hash of the client address (for IPv6, its /64 prefix), with the
salt rotated hourly and never persisted (connections over the onion service have no address and share one generous ceiling
instead). There is no CAPTCHA and no proof-of-work: both would need either a third party or
client-side script, and the site runs neither. Published statistics are counts and distributions;
no mean, average, or sum of any scale is ever published, so a burst of extreme reports cannot move
a headline number. A coordinated-submission detector runs on the raw store; what it flags is
listed by log position, leaves the tables in batches of at least five (see *Small-cell disclosure
and differencing*), and is summarised in the *Integrity log* section of each release page. This
is the weakest control in the design and is described as such in
[What we can and cannot promise](WHAT-WE-CAN-AND-CANNOT-PROMISE.md).

*Stated limit:* an identifier-free system cannot prove submissions come from distinct people. We
make fabrication costly and detectable, and we publish what we detect. We do not claim the data is
clean.

### Operator misuse and succession

*Threat:* a future operator, acquirer, or trustee uses the data in ways contributors did not agree
to.

*Enforced:* the data that could be misused does not exist in reconstructable form — there is no
row-level dataset that identifies anyone, no key table, and no contact list. The terms contain an
irrevocable commitment never to sell, license, or transfer row-level data. The shutdown protocol in
[SHUTDOWN.md](SHUTDOWN.md) specifies destruction. This is a stronger promise than an organizational
form: the 23andMe database was transferred in bankruptcy to a nonprofit controlled by its own
founder.

### Silent revision of published numbers

*Threat:* a published statistic is changed after the fact, or a release is withdrawn.

*Enforced:* every release is a signed git tag whose hash is submitted to a public transparency log
we do not control. The release specification's hash is submitted before the first report is
accepted. The
Merkle root of the submission log is published with each release. Releases are never deleted.

## What this design does not do

- It does not offer edit or deletion after confirmation. There is no identifier with which to
  locate a report, and building one would defeat the purpose. See
  [What we can and cannot promise](WHAT-WE-CAN-AND-CANNOT-PROMISE.md).
- It does not verify that any report is truthful.
- It does not provide differential privacy on published releases in version 1. Suppression and
  bounded table counts are the release controls. This may change; if it does, it will be stated in
  a versioned release specification, never described as a property of the site or the store.
- It does not prove that the deployed server runs the published code. The code is public so that
  what it *would* do can be examined; the transparency log makes published *outputs* checkable.
  We do not claim more than that.

## Change control

This document is versioned. A change to any enforced mitigation requires a version increment,
a changelog entry, and — if the change weakens a protection — a notice on the site before it takes
effect. The schema and release specification are frozen at launch and changed only on a published
schedule.
