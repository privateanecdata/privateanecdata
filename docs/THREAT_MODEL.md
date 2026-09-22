# Threat model

**Version 0.1 — draft, pre-launch.** This document is written as a specification: it states what
the system enforces, not what it worries about. Every mitigation listed here is either implemented
in code, enforced in CI, or stated as a published operating commitment. Where a risk cannot be
removed, that is stated in [What we cannot protect you from](WHAT-WE-CANNOT-PROTECT-YOU-FROM.md).

## What this system is

A public website that accepts one-time, structured, identifier-free reports about the use of
peptides obtained outside the regulated supply chain, and publishes aggregate statistics computed
from those reports under a release specification fixed before any data was collected.

## Assets

In priority order:

1. **The contributor's identity** — never collected, so never held.
2. **The association between a report and a person** — the only thing that could convert a
   report about gray-market drug use into a fact about a specific human. The design's purpose is
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

A single HTTP POST at the moment the contributor confirms, containing only fields drawn from the
frozen controlled vocabularies in [SCHEMA.md](../spec/SCHEMA.md). Specifically:

| Field | Form |
|---|---|
| Compound | One of a frozen list; rare entries are published only rolled into a mechanism class |
| Primary goal | One of that compound's predefined goal list |
| Source channel | One of seven types; never a vendor, pharmacy, or brand name |
| Starting and current dose | A band, never a number |
| Frequency, titration pattern, duration | Buckets |
| Purity testing | Obtained / matched label / did not match / did not test |
| Reconstitution practice | Coarse categories |
| Outcome for the stated goal | No change / slight / moderate / large |
| Adverse effects | Multi-select from a fixed list, each with an onset bucket and whether it resolved on stopping |
| Status | Still taking, or stopped in which week bucket and the primary reason from a fixed list |
| Age band, sex | Optional; six bands and three options |

**Not received, by construction:** name, email, phone, account, cookie, contribution key, IP
address (see *Network*), free text of any kind, exact dose, exact dates, start date or quarter,
vendor or pharmacy name, price, location at any granularity, device identifiers, or any field not
listed in the schema.

Coarsening happens **in the browser before transmission**. The server does not receive the exact
value and round it; it receives the rounded value. The form works with JavaScript disabled, in
which case the coarse options are the only options presented.

## What the server stores

Exactly the fields above, plus a day-granularity received date assigned on write, a per-row
secret salt, and — in a separate log table, not on the row — the position of the row's Merkle
leaf. Nothing else. There is no session table, no
draft table, no request log that references submissions, and no column that could hold an
identifier.

**Nothing is stored until the contributor confirms.** Multi-step form state is carried in the
request and rendered back to the contributor for review. Abandoned forms leave no record.

Every stored row is appended, with a per-row secret salt, to a Merkle log whose root is published
periodically (see *Integrity*). Rows are never updated. Rows excluded from analysis for quality
reasons are recorded in a separate, separately-published exclusion list with reason codes; they are
not deleted from the log.

## What is published

Only the outputs enumerated in [RELEASE_SPEC.md](../spec/RELEASE_SPEC.md), which was fixed and
witnessed in a public transparency log before the first report was accepted. Each release is a
set of static files generated by a pipeline whose code is public, reviewed by a person before
publication, and committed with a signed tag.

The specification lists every table that will ever be published and the rule for every cell. No
table is added in response to a request. No interactive query interface exists. No row is ever
published, licensed, shared with a researcher, or otherwise disclosed, in any form, de-identified
or otherwise.

## Enforced mitigations, by threat

### Direct identification

*Threat:* a name, email, or contact detail arrives with a report.

*Enforced:* no such field exists in the form or the schema. There is no free-text field in the DOM.
CI fails on any form element not enumerated in the schema.

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
at any dataset size below tens of thousands. We publish the uniqueness analysis that quantifies
this. This is why the raw store is never published and why we hold nothing else.

### Timing correlation

*Threat:* a submission timestamp is matched to a public post timestamp.

*Enforced:* no timestamp finer than a day is written to any durable store. A report is committed
at the moment of confirmation, so the Merkle log preserves order of commitment; that order is
recoverable by us, and by anyone who obtains the store, only to within the day the received date
already gives. The published leaf list is in log order, but a leaf cannot be matched to a report
without that report's secret salt, which is never published. Row IDs are random. No real-time
feed exists; counts are published only with releases.

### Network metadata

*Threat:* the contributor's IP address, TLS fingerprint, or user agent is recorded alongside the
submission.

*Enforced:* access logging is disabled at every layer we control — web server, reverse proxy, TLS
termination, and application. There is no CDN, WAF, or third-party edge in front of the origin. TLS
session tickets and session IDs are disabled on the submission origin. `Referrer-Policy:
no-referrer` is set and query parameters are rejected on the intake route. A Tor onion service
provides a second path with no IP for us to receive. The hosting provider necessarily receives the
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
and a display threshold below which no proportion is shown. Rare compounds are published only
rolled into their mechanism class. No table is cross-tabulated on a rare compound. Releases are
cumulative snapshots; the exclusion of quality-flagged rows is applied identically to every
release so that no differencing between releases isolates a row. The total number of distinct
tables that will ever be published is bounded by the specification.

*Stated limit:* a suppression threshold is not a privacy guarantee. An adversary who can submit
crafted reports can push a target's cell over any threshold. This is why the number of tables is
bounded, why no interactive querying exists, and why the specification cannot be extended on
request.

### Fabricated submissions

*Threat:* one party submits many reports to move a published number.

*Enforced:* client-side proof-of-work on submission, self-hosted, with no identifier and no
third-party service. In-memory rate limiting keyed on a salted hash of the client address, with
the salt rotated hourly and never persisted. Published statistics use robust estimators (medians,
trimmed means, interquartile ranges) rather than means. A coordinated-submission detector runs on
the raw store and its findings are published as a running integrity log.

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
we do not control. The release specification's hash was submitted before any data existed. The
Merkle root of the submission log is published with each release. Releases are never deleted.

## What this design does not do

- It does not offer edit or deletion after confirmation. There is no identifier with which to
  locate a report, and building one would defeat the purpose. See
  [What we cannot protect you from](WHAT-WE-CANNOT-PROTECT-YOU-FROM.md).
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
