# Subprocessors

Every third party that receives any request from a visitor to this site, or that holds any part
of the submission store. This list is short on purpose and is part of the product.

| Party | Role | Region | What it receives | Its retention policy |
|---|---|---|---|---|
| **[Hosting provider]** | Runs the server | [US region] | IP address and request metadata of every clearnet request, as a necessary consequence of delivering the page. We do not log it; we cannot promise the provider's own network layer does not. | [link to provider policy] |
| **Tor network** | Second path to the site | — | Nothing attributable. Onion routing means no party on our side receives a client IP. | n/a |

**That is the complete list.**

There is no CDN, no WAF, no DDoS-protection edge, no analytics service, no error-reporting
service, no email service, no font host, no CAPTCHA service, no third-party JavaScript, no
payment processor, and no data processor of any other kind. The Content-Security-Policy header
permits no external origin, and the build fails if any resource references one.

Registrar and DNS for the domain are operational vendors that see DNS queries in the ordinary
way and receive nothing about any submission; they are named here for completeness:
**[registrar]** (domain), **[DNS provider]** (authoritative DNS).

Backups of the submission store are encrypted at rest and held with **[hosting provider /
backup location]**. Backups contain the same fields as the store and nothing more.

## Changes

Any addition to this list is a material change to what contributors were told when they
submitted. An addition is published here at least one full release period before it takes
effect, with a notice on the site.

*Last updated: [date]. Operator: [legal entity], an Oregon limited liability company.*
