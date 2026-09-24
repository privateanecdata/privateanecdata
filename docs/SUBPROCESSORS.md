# Subprocessors

Every third party that receives any request from a visitor to this site, or that holds any part
of the submission store. This list is short on purpose and is part of the product.

| Party | Role | Region | What it receives | Its retention policy |
|---|---|---|---|---|
| **DigitalOcean** | Runs the server | United States (New York, NYC1) | IP address and request metadata of every clearnet request, as a necessary consequence of delivering the page. We do not log it; we cannot promise the provider's own network layer does not. | [DigitalOcean privacy policy](https://www.digitalocean.com/legal/privacy-policy) |
| **Tor network** | Second path to the site (onion address: `unxzqdwshn2ftzivh3bg7e63mvn3ccsxs2d5oplxd7z3djs3qvppjhyd.onion`) | — | Nothing attributable. Onion routing means no party on our side receives a client IP. | n/a |
| **Google (Gmail)** | The project's mailbox, used to send replies | United States | When we reply to a contact message: the address the sender gave, and our reply. Contact messages themselves are read on our server and are not sent to it. Nothing about reports. | [Google privacy policy](https://policies.google.com/privacy) |

**That is the complete list.**

There is no CDN, no WAF, no DDoS-protection edge, no analytics service, no error-reporting
service, no email-sending service, no font host, no CAPTCHA service,
no third-party JavaScript, no payment processor, and no data processor of any other kind. Our
server sends nothing to anyone except the pages it serves; contact messages stay on it, and
retention is as stated in [LEGAL-PROCESS.md](LEGAL-PROCESS.md). The Content-Security-Policy header
permits no external origin, and the build fails if any resource references one.

Registrar and DNS for the domain are operational vendors that see DNS queries in the ordinary
way and receive nothing about any submission; they are named here for completeness:
**Porkbun** (domain registrar and authoritative DNS).

Backups of the submission store are encrypted to a key held only by the operator, and kept on the
same DigitalOcean server; no copy is held anywhere else. Backups contain the same fields as the
store and nothing more.

## Changes

Any addition to this list is a material change to what contributors were told when they
submitted. An addition is published here at least one full release period before it takes
effect, with a notice on the site.

*Last updated: 22 September 2026. Operator: at present an individual in Oregon, United States, as stated in the [privacy statement](PRIVACY.md), until the project incorporates.*
