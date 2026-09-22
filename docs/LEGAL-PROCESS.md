# Legal process and data retention

**Draft — for review by counsel before publication.**

This page states what we hold, for how long, and what we do when someone with legal authority
asks for it. It is written so that a contributor can read it before deciding whether to submit.

## What we hold

The submission store, as described in [SCHEMA.md](../spec/SCHEMA.md): one row per report,
containing only the coarsened, controlled-vocabulary fields listed there, a received date at day
granularity, and a per-row secret salt used for the Merkle log. That is the complete list.

We do not hold, at any layer we control: IP addresses, user agents, session records, cookies,
accounts, email addresses, names, exact timestamps, exact doses, vendor names, locations, or any
free text. Access logging is disabled on the web server, the reverse proxy, and the application.
There is no CDN, WAF, or third-party edge in front of the origin. The configuration that disables
logging is in the public repository.

We also hold: the public source code; the release artifacts, which are public; the exclusion list,
which is public; and ordinary operational records (billing with our host, DNS, certificates) that
contain nothing about any contributor.

## Retention

- **Submission rows:** retained indefinitely. There is no identifier with which to delete a
  specific row, and the rows are the dataset. See
  [What we cannot protect you from](WHAT-WE-CANNOT-PROTECT-YOU-FROM.md).
- **Web server, proxy, and application logs:** not written. Retention is zero because there is
  nothing to retain.
- **Rate-limiter state:** in memory only, keyed on a salted hash of the client address with the
  salt rotated hourly and never written to disk. Nothing survives a process restart.
- **Backups:** the submission store is backed up. Backups contain the same fields as the store and
  nothing more. Backups are encrypted and retained for [N] days.
- **Contact messages:** if you write to us, we retain your message only as long as needed to
  respond and then delete it. We ask that you not describe your own submission in a message to
  us, because that message would be more identifying than anything in our database.

## What our hosting provider holds

Our hosting provider is named in [SUBPROCESSORS.md](SUBPROCESSORS.md), with its region and a link
to its own retention policy. To deliver the site, the provider necessarily receives the IP address
of every request. We do not control the provider's own network logging and we do not claim it
does not exist. If that matters to you, the site is reachable as a Tor onion service, in which
case there is no IP for anyone on our side to receive.

## What a legal request would obtain

If we are served with valid legal process requiring us to produce what we hold, we will comply
with it. What can be produced is: the submission store as described above; the public
repository; the public releases; and our operational records. None of these contains a field
that identifies a contributor, and we hold no auxiliary data with which to attempt an
identification.

We will not create, for the purpose of responding to a request, a linkage or analysis we do not
otherwise perform. In particular, we will not run a content-based search of the store to locate a
specific person's report: that is the re-identification our design exists to prevent, and it is
the act that a public commitment not to re-identify — which we have made, and which is a
statutory element of the de-identification standards we rely on — forbids.

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
publish notice of the event on this page and in the next release's integrity log.

---

*Operator: [legal entity name], an Oregon limited liability company. Governing law: Oregon.*
