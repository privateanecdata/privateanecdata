# What we can and cannot promise

## What we promise

- **We hold nothing that identifies a report.** The report form asks for no name, email, account,
  phone, cookie, key, or location; none is stored with a report; and your network address is never
  written down.
- **We will never try to work out who you are**, and we will never let anyone else use our data to.
- **Your report is never shown to anyone.** Not to researchers, not to a buyer, not in a wind-down.
  Only aggregate statistics are published, under [rules fixed in advance](../spec/RELEASE_SPEC.md).
- **The count is checkable.** Every accepted report is committed to a public log anyone can verify.
- **Nobody pays us and we pay nobody.**

The rest of this page is the other half — the things a careful design still cannot do, stated
without softening, because you should know them before you contribute. The whole approach is in
the [privacy protocol](PRIVACY-PROTOCOL.md).

## What we cannot promise

Most sites that collect health information tell you what they do to protect it. This page tells
you what we cannot do, so you can decide with that in front of you.

### Your report might point at you on its own

We never ask who you are. But a report about an uncommon compound, taken at an unusual dose, by
someone in a less common age group, is a small enough description that it could match only a few
people — and if you have described the same thing publicly, somewhere you can be identified, then
someone who obtained our database and also read your post could shortlist your report.

We do three things about this. The form only asks for rounded answers — a range, a bucket, a kind — so the
database holds a dose *band* rather than your dose and a duration *bucket* rather than your start
date. We never hold your location, at any granularity. And we never publish individual reports —
only aggregate statistics, under rules fixed before we collected anything.

What we cannot do is make a detailed report about a rare drug indistinguishable from other
reports when there are few other reports. We publish an analysis quantifying this. If the compound
you use is rare and you have discussed your use publicly under a name that can be traced to you,
you should weigh that before submitting.

### We cannot delete your report after you submit it

There is no account, no email, no key, and no identifier of any kind attached to your report.
That is the point: it means nobody — not us, not someone who takes our database, not a court that
orders us to hand it over — can find *your* report among the others.

The consequence is that we cannot find it either. If you write to us and describe your report, we
will not search for it: doing that would be exactly the re-identification we designed against, and
we could not confirm the report was yours in any case.

Before you submit, you will see everything you are about to send, and you can go back and change
it. Nothing is stored until you confirm. After you confirm, submission is final. If that is not
acceptable to you, please do not submit.

This is the ordinary condition of survey research that collects no identifiers, and consent
forms for such studies have said so for decades. We are saying it here so it is not a surprise.

### We cannot promise our hosting provider has never seen your IP address

When your browser loads this site, the company that hosts our server receives your IP address in
order to deliver the page. That is how the internet works. We do not log it, we do not store it,
and we have configured every layer we control not to. We publish who our host is, where the server
is, and what their own retention policy says.

If that is not enough, use our Tor onion address. Over Tor there is no IP address for anyone on
our side to receive.

### We cannot prove the server runs the code we published

Our source code is public. You can read what it does. But you cannot verify from your browser that
the server you are talking to is running that code and not something else. No website can offer
that proof, and we are not going to pretend otherwise.

What we can make checkable is the *output*. Every set of statistics we publish is committed to a
public log we do not control, along with a fingerprint of our submission database. You can verify
that a number we published today is the number we published, and that our count of reports is the
count we committed to. That is a narrower guarantee than "trust the server," and it is the one we
can actually keep.

### We cannot stop someone from submitting false reports

Anyone can submit. We do not ask for identity, so we cannot prove that two reports come from two
people, or that any report is truthful. A vendor with a commercial interest in a compound could
submit many reports to move a statistic.

We make this detectable rather than impossible: a bot trap catches automated submitters, an
in-memory rate limit slows any one connection, a coordinated-submission detector (public code:
`tools/detect.py`) flags self-contradicting reports and unusual bursts, and what it flags is
listed in every release's *Integrity log* section and leaves the tables in batches of at least
five. We publish only counts and
distributions — never an average — so a burst of extreme reports cannot move a headline number.
There is no CAPTCHA and no proof-of-work: both would need a third party or a script in your
browser, and this site runs neither. We do not claim the data
is clean, and you should not read any number here as if it were.

### We cannot resist a lawful order to produce what we hold

If we are served with valid legal process, we will comply with it. What we hold is a set of rounded
reports with no field that identifies anyone, and we hold nothing else that could be used to try.
We will challenge overbroad requests where we can, and we describe our handling of legal process
in a separate document. But you should assume that anything we hold could one day be produced, and
submit only what you would be comfortable having produced under those conditions.

### We cannot tell you whether anything here works or is safe

Every report on this site is something a person chose to tell us, about themselves, after the fact,
with no verification. People who had bad experiences may be more or less likely to report than
people who had good ones. People expect things to work and report accordingly. The compounds
themselves vary in what is actually in the vial.

The Federal Trade Commission's own guidance states that anecdotal evidence, including surveys of
consumer experiences, is never sufficient to substantiate claims about the effects of a health
product. We agree. Nothing here is evidence that any compound is effective or safe. What it is, is
a structured record of what people say happened to them, with the number of people shown next to
every figure, published under rules we cannot quietly change.

### We cannot promise to exist forever

Projects like this usually end. When this one does, the shutdown protocol we publish specifies that
the submission database is destroyed. Because no row identifies anyone, there is nothing in it that
would be worth transferring, and we have committed in our terms never to transfer it.

---

*If you have read this far and still want to contribute, thank you. The rest of the site explains
what we do with what you send.*
