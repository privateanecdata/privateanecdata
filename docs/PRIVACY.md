# Privacy

**Version 1.1 — effective 24 September 2026.** Changed from 1.0 (22 September 2026): contact
messages are read on our server and are no longer emailed to the operator's mailbox.

This is a short document because there is not much to say. We designed the site so that we hold
nothing that identifies you, and this page tells you exactly what that means, what we do hold,
and what we cannot do as a result.

## Who we are

Private Anecdata is run by an individual in Oregon, United States, who will be named here when
the project incorporates. Every commitment on this page binds the operator now and any successor
entity then; see [Terms](TERMS.md) §4 and §11. Contact: the [contact page](/contact). Oregon law
governs. The complete list of third parties involved in running the site is in
[Subprocessors](SUBPROCESSORS.md); it has [two] entries.

## What a report contains

When you contribute, you answer a fixed set of multiple-choice questions about one compound:
which compound, how you used it (route, dose range, frequency), where it
came from (the kind of source, never the vendor), how long you took it, whether you had it tested,
what you were hoping for and what you observed, any effects from a fixed list
with when they started and whether they stopped, whether you are still taking it, and — optionally
— an age band and sex. Every question offers only rounded answers: a dose range rather than a
milligram, a duration bucket rather than dates, a kind of source rather than a name. There is no
free-text question anywhere on the report form, and nothing you could type there is ever stored:
the server accepts only values from the fixed lists. (The page contains one invisible text box that exists
to catch automated submitters; anything in it causes the submission to be discarded.) The complete field list and every allowed value is in the
[schema](../spec/SCHEMA.md).

The server adds the day it received the report — the day, not the time — and a random secret
value used only to commit the report to the public append-only log described in
[How we count reports](RELEASE-SPEC-SUMMARY.md#how-we-count). That is the complete record.

## What we do not ask for and do not record

No name. No email address. No account. No phone number. No location of any granularity — not
your country. No date of birth. No cookie, and no identifier stored in your browser. No free
text. No vendor, pharmacy, clinic or brand.

We do not log your IP address with any request. The web server's access logging is off. Two
exceptions, stated because they are true: if a TLS connection fails before it becomes a request,
the web server writes the failing address to a process log; and if the web server cannot reach
the application (for example during a restart), it logs the error with the address, headers and
path deleted by our configuration. Both logs live in memory and expire within a day.
The application keeps no request log. The hosting configuration is published in the repository so
this can be checked.

Two things touch your network address without recording it. To limit abuse, the application
computes a hash of your address together with a random value that changes every hour, keeps the
count in memory only, and never writes it to disk; after an hour it is unrecoverable even by us. Our host necessarily sees network traffic to reach us; what it retains
is stated in [Subprocessors](SUBPROCESSORS.md) and [Legal process](LEGAL-PROCESS.md).

The site loads nothing from anyone but us: no analytics, no fonts, no scripts, no embedded
content, no CAPTCHA service. Your browser's network panel should show one host. This is enforced
by a check that fails our build if it is ever untrue.

We do not track you, so "Do Not Track" and "Global Privacy Control" signals are honored by
construction. We do not sell personal information, share it for advertising, or use it for
profiling, because we do not have it.

## De-identified by design

A report is not linked to you. It contains no direct identifier, no persistent identifier, and no
field that could serve as one. The questions are coarse on purpose, so that the record cannot be
matched to a person from what it contains. We have published an analysis of how distinctive a
single report is on several combinations of fields, and we re-run it on the real store before
every release and publish the summary; see the [schema](../spec/SCHEMA.md) and the *Uniqueness of
the store* section at the end of any release page.

**We commit, publicly and without exception, that we will not attempt to re-identify any
individual from any report, and that we will not allow anyone else to.** We do not search the
store for a particular person's report for any reason, including at that person's request; doing
so would itself be an attempt at re-identification. The reports themselves are never released to
anyone in any form — see [What we publish](#what-we-publish) — so there is no recipient who could
attempt it either. This commitment is the one this statement exists to carry, and it binds us
from the moment the first report is accepted.

## What we publish

Only the aggregate statistics listed in the [release specification](../spec/RELEASE_SPEC.md),
which will be witnessed in a public log before the first report is accepted and cannot be
extended without notice. Small groups are suppressed. Individual reports are never displayed,
published, shared with researchers, licensed, sold, or transferred, de-identified or otherwise,
to anyone, for any reason, including in a sale, merger, insolvency or wind-down of the operator.
The one exception we cannot rule out is valid legal process, which could compel production of the
store; [Legal process](LEGAL-PROCESS.md) explains what that would obtain, and nothing in the
store identifies anyone. If this project ends, the store is destroyed; see
[Shutdown](SHUTDOWN.md).

## What we cannot do

**We cannot find, correct, or delete your report after you submit it.** Nothing in the report
points back to you, and we keep nothing that does — so we have no way to tell which report is
yours, and no way to confirm that a request about a report comes from the person who submitted
it. This is the ordinary condition of a survey that collects no identifiers, and it is the
reason the design protects you: the same property that stops us from finding your report stops everyone else. The
form says this plainly on the final screen before you submit. If it is not acceptable, do not
submit.

If you write to us asking us to locate or remove a report, we will reply by pointing to this
section. Please do not describe your report in that message: a description of your report next to
your email address is more identifying than anything we hold. Do not send it.
A message sent through the contact page is the one thing you can type on this site. It is stored
on our server and read there by the operator; it is not emailed anywhere. If you give an email
address and we reply, the reply is sent from the project's mailbox at the provider named in
[Subprocessors](SUBPROCESSORS.md), so that provider receives your address and our reply. The
message is used for nothing but replying, and deleted once we have replied and in any case within
30 days of receipt. Give an email address only if you want a reply; it is deleted with the
message.

## Age

The site is for adults. The youngest age band the form offers is 18–24. Do not contribute if you
are under 18.

## Where this service is offered

This service is offered from the United States, in English, under Oregon law. It is not directed
to, and we do not monitor, people in the European Economic Area, the United Kingdom, or
Switzerland.

## Changes

This statement is versioned. Every version is in the public repository, and the hash of each
version is submitted to a public transparency log when it takes effect, so a change cannot be
quiet or backdated. A change that reduces what we promise here does not apply to reports
received before it took effect — and since we cannot separate reports by contributor, in practice
it cannot apply to the store at all.

## Words we do not use

We do not call reports "anonymous." No data is beyond all possible association with a person,
so we tell you what we hold and what could still give you away — see
[What we can and cannot promise](WHAT-WE-CAN-AND-CANNOT-PROMISE.md) — instead of using a word
that promises more than anyone can deliver. "De-identified" has a specific meaning: no identifiers,
reasonable measures against re-identification, a public commitment not to attempt it, and
contractual limits on anyone who receives the data. Those are the four things this page
describes.
