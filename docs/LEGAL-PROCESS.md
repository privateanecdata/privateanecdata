# Legal process and data retention

**Version 1.0 — effective 22 September 2026.**

This page states what we hold, for how long, and what we do when someone with legal authority
asks for it. It is written so that a contributor can read it before deciding whether to submit.

## What we hold

The submission store, as described in [SCHEMA.md](../spec/SCHEMA.md): one row per report,
containing only the coarsened, controlled-vocabulary fields listed there, a received date at day
granularity, and a per-row secret salt used for the Merkle log. That, plus any contact messages
not yet deleted (below), is the complete list.

The submission store and the site hold none of: IP addresses, user agents, session records,
cookies, accounts, email addresses, names, exact timestamps, exact doses, vendor names,
locations, or any free text. (A message you send through the contact page is the one place free
text, and optionally an email address, reaches us; see *Contact messages* below.) Access logging is disabled on the web server, the reverse proxy, and the application.
There is no CDN, WAF, or third-party edge in front of the origin. The configuration that disables
logging is in the public repository.

We also hold: the public source code; the release artifacts, which are public; the exclusion list
(the reports the detector excluded, which leave the published tables in batches, listed by log
position and date in every release), which
is public; and ordinary operational records (billing with our host, DNS, certificates) that
contain nothing about any contributor.

## Retention

- **Submission rows:** retained indefinitely. There is no identifier with which to delete a
  specific row, and the rows are the dataset. See
  [What we can and cannot promise](WHAT-WE-CAN-AND-CANNOT-PROMISE.md).
- **Web server, proxy, and application logs:** no access or request log is written. Process
  logs (startup, certificate renewal, errors) are kept in memory and expire within a day. An
  address can reach them two ways: a TLS connection that fails before it becomes a request is
  logged with its address, and a handler error (for example a 502 during a restart) is logged with
  the request's address, headers and path deleted by our configuration.
- **Rate-limiter state:** in memory only, keyed on a salted hash of the client address (for IPv6,
  its /64 prefix) with the salt rotated hourly and never written to disk. Nothing survives a process restart.
- **Backups:** the submission store is backed up. Backups contain the same fields as the store and
  nothing more. Backups are encrypted and retained for 30 days.
- **Contact messages:** a message sent through the contact page is stored on our server and
  forwarded to the operator's mailbox. We delete it once we have replied, and in any case no later
  than 30 days after receipt. The mailbox provider is named in [SUBPROCESSORS.md](SUBPROCESSORS.md). We ask that you not describe your own submission in a message to
  us, because that message would be more identifying than anything in our database.

## What our hosting provider holds

Our hosting provider is named in [SUBPROCESSORS.md](SUBPROCESSORS.md), with its region and a link
to its own retention policy. To deliver the site, the provider necessarily receives the IP address
of every request. We do not control the provider's own network logging and we do not claim it
does not exist. If that matters to you, the site will also be reachable as a Tor onion service at
the address published in [SUBPROCESSORS.md](SUBPROCESSORS.md) once it is live; over the onion
service there is no IP for anyone on our side to receive.

## What a legal request would obtain

If we are served with valid legal process requiring us to produce what we hold, we will comply
with it. What can be produced is: the submission store as described above; any contact messages
not yet deleted, including any reply address the sender gave; the public repository; the public
releases; and our operational records. Nothing in the submission store contains a field that
identifies a contributor, and we hold no auxiliary data with which to attempt an identification
— which is also why a contact message must never describe a report.

We will not create, for the purpose of responding to a request, a linkage or analysis we do not
otherwise perform. In particular, we will not run a content-based search of the store to locate a
specific person's report: that is the re-identification our design exists to prevent. We have
publicly committed not to attempt it, and we will not.

We will challenge requests that are overbroad, that seek data we do not hold, or that seek to
compel us to re-identify, to the extent the law permits. We will not describe this as protection
for any individual contributor. It is a description of what we will do.

## Preservation requests

A preservation request asks us to keep what we have and not delete it. Because we already retain
submission rows indefinitely and write no logs, a preservation request changes nothing about
what exists. It does not cause us to begin logging anything.

## Notice

We do not have any contributor's contact information, so we cannot notify any individual of a
request concerning their report. If we receive legal process that concerns the submission store,
and we are not prohibited from doing so, we will say so on this page, with the date and the
general nature of the request. We do not operate a warrant canary and do not describe this page
as one; no court has held that a canary protects anyone, and we will not imply otherwise.

## Breach

If the submission store is accessed without authorization, what is exposed is the set of rows
described above. Because no row identifies a person, we cannot notify individuals. We will
publish notice of the event on this page and in the *Integrity log* section of the next release.

---

*Operator: at present an individual in Oregon, United States, as stated in the [privacy statement](PRIVACY.md), until the project incorporates. Governing law: Oregon.*
