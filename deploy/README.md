# Deploying

One US VPS. Caddy in front, the Node server on loopback, SQLite on local disk. No CDN, no WAF,
no third-party edge.

## Layout

```
/srv/private-anecdata/
  app/          the built app (this repo's app/ after `npm run build`)
  docs/ spec/   copies of the repo's docs/ and spec/ — the app reads them at build time, beside it
  data/         reports.db and its WAL — owned by the service user, mode 0700
  releases/     published releases, written by tools/release.py — read-only to the service
```

## Steps

**`deploy/setup.sh` does all of the below on a fresh Ubuntu 24.04 host** — run it as root, answer
three questions (hostname, contact mailbox, backup public key), and read the summary it prints.
Safe to rerun. The numbered steps are what it does, for reading and for doing by hand.

1. Create the service user: `useradd -r -s /usr/sbin/nologin anecdata`.
2. Build **on the host, with the public hostname set**: `cd app && PA_HOST=privateanecdata.org npm run build:prod`.
   `PA_HOST` is read by `astro.config.mjs` at build time (it becomes `security.allowedDomains`),
   not at run time; a build made without it rejects every clearnet form POST with 403 and sees
   every client as loopback. `build:prod` refuses to run without it. Then `npm ci --omit=dev`.
3. `mkdir -p /srv/private-anecdata/data && chown anecdata:anecdata /srv/private-anecdata/data && chmod 700 /srv/private-anecdata/data`.
4. Install `private-anecdata.service` to `/etc/systemd/system/`, `systemctl enable --now private-anecdata`.
5. Install Caddy. Put `Caddyfile` at `/etc/caddy/Caddyfile` with the real hostname.
6. **TLS session resumption — open item.** The threat model says session tickets are disabled on
   the submission origin. Caddy rotates ticket keys automatically and does not persist them, but
   whether tickets can be turned off per-site in the current Caddy release has not been verified.
   Verify against the Caddy docs for the installed version before publishing that claim; until
   then, state the rotation behaviour rather than "disabled."
7. `systemctl enable --now caddy`.
8. Full-disk encryption on the VPS volume. Backups of `data/` encrypted to the public key at
   `deploy/backup.pub`, whose private half does not live on the host; retention stated in
   `docs/LEGAL-PROCESS.md`.
9. `mkdir -p /srv/private-anecdata/releases`. The service reads it (`PA_RELEASES_DIR`) and
   serves it under `/releases/`; it never writes there.

## Making a release

Monthly for the twelve months after the first release, then quarterly, by hand, on the host. Ids are `YYYY-MM` while monthly
and `YYYY-QN` once quarterly. The store is readable only by the service user (`data/` is 0700), so
the steps that touch it run as that user; signing runs as you, with your key. **Always pass
`--prior` after the first release:** it chains the log and it is what the batch-update rule in
`RELEASE_SPEC.md` is computed against (the pipeline prints which tables it republishes unchanged).

```
cd /srv/private-anecdata/repo                                  # a checkout of this repository
sudo -u anecdata python3 tools/detect.py scan --db ../data/reports.db --out ../data/candidates.json
#   review ../data/candidates.json — remove anything you do not agree with — then:
sudo -u anecdata python3 tools/detect.py apply --db ../data/reports.db ../data/candidates.json --date YYYY-MM-DD
#   --date must be after the prior release's date and on or before this release's: the pipeline refuses
#   an exclusion dated behind the prior release (backdated) or after this one
sudo -u anecdata rm ../data/candidates.json
sudo -u anecdata python3 tools/release.py --db ../data/reports.db --id 2026-12 --date 2026-12-31 \
    --out ../data/staging/2026-12 --prior ../releases/2026-11     # the very first release: --first instead of --prior
sudo -u anecdata python3 tools/verify_release.py ../data/staging/2026-12 --prior ../releases/2026-11 \
    --spec spec/RELEASE_SPEC.md --taxonomy spec/taxonomy.v1.json --db ../data/reports.db
#   read every table against RELEASE_SPEC.md before going further
sudo mv ../data/staging/2026-12 ../releases/2026-12 && sudo chown -R root:root ../releases/2026-12
tools/witness.sh all ../releases/2026-12                       # sign, Rekor, OpenTimestamps — as you
python3 tools/verify_release.py ../releases/2026-12 --pubkey releases/pubkey.pem   # once more, as anyone would
git add releases/2026-12 && git commit -S -m "release 2026-12" && git tag -s release/2026-12
tools/witness.sh upgrade ../releases/2026-12                   # a day later, then commit the upgraded .ots
```

`detect.py apply` is the only write to the store that is not the form; it adds rows to the
`exclusions` table and touches nothing else. The signing key lives in `~/.config/private-anecdata/`
of the releasing user, mode 0600, never on the service user and never in the repository.

## What is and is not logged

- **Caddy:** `log { output discard }` in each site block — no access log. Process logs to
  journald contain startup, certificate, and error lines. Two caveats stated honestly: a TLS
  handshake failure is logged by the Go HTTP server with the remote address that failed (a
  connection that never became a request); and a handler error such as a 502 while the app
  restarts is logged on the *default* logger with the request attached — the global `log default`
  filter in the Caddyfile deletes the address, port, headers and path from those entries. Keep
  both the filter and the journald cap.
- **App:** writes nothing per request. The only startup line is the adapter's "listening on". An
  uncaught render error prints a stack trace with the request path (`/contribute`), never a body,
  header, or address.
- **journald:** set `Storage=volatile` and `MaxRetentionSec=1day` in
  `/etc/systemd/journald.conf.d/private-anecdata.conf` so process logs live in memory and expire
  within a day; nothing request-level is ever in them.
- **Kernel / netfilter:** do not enable connection logging.
- **Rate limiter:** Caddy forwards the client address; the app hashes it (an IPv4 address, or an
  IPv6 /64 so one household is one bucket) with an hourly in-memory salt (`src/lib/abuse.ts`)
  and keeps a count for the hour. Nothing is written to disk
  and nothing survives a restart. Astro trusts the forwarded header only when the Host is the
  `PA_HOST` the app was built with.

## Contact form

`/contact` stores each message in `/srv/private-anecdata/data/contact.db` (`PA_CONTACT_DB_PATH`,
separate file from the reports store) and, when `PA_CONTACT_TO` is set in the unit, forwards it
over plain SMTP to `PA_SMTP` (default `127.0.0.1:25`). Install `postfix` as a null client that
listens on loopback only and relays outbound to the operator's mailbox; set `PA_CONTACT_FROM` to
an address at the site's domain and publish an SPF record for the host so the mail is accepted.
Use a mailbox dedicated to the project as `PA_CONTACT_TO` (not a personal address): a reply sent
from it reaches the sender, and until the project is incorporated the operator is not named.
No set-gid helper is involved, so the unit's hardening stays as shipped. If the relay is down the
message is still stored and a one-line error (no content) goes to the journal. The address is
never rendered anywhere. Messages are the one free-text store on the host: `deploy/prune-contact.sh`
from cron (daily) deletes them inside the 30 days the privacy statement promises, and
`sqlite3 /srv/private-anecdata/data/contact.db 'SELECT received_day, reply_to, body FROM messages'`
reads them over SSH if forwarding ever fails.

## Regional block (optional, off by default)

The plan allows declining clearnet connections from the EEA, UK and Switzerland as evidence of
non-targeting. It is not built into this configuration. If enabled, do it in Caddy with a GeoIP
module (for example `caddy-maxmind-geolocation` against a locally held MaxMind database) as an
in-memory lookup that returns a plain 403 and logs nothing — then say so in `docs/PRIVACY.md`
and in the *Location* paragraph of `docs/PRIVACY-PROTOCOL.md` **before** switching it on (both
currently state that no geographic lookup happens). The onion service cannot be region-blocked
and the documents must not claim otherwise.

## Tor onion service

Install `tor`; in `/etc/tor/torrc`:

```
HiddenServiceDir /var/lib/tor/anecdata/
HiddenServicePort 80 127.0.0.1:8081
```

Port 8081 is Caddy's onion site block, not the app. Routing the onion path through Caddy matters:
tor hands the client's request through untouched, so a client could otherwise send its own
`X-Forwarded-For`/`X-Forwarded-Host` straight to the app and mint a fresh rate-limit bucket per
request. Caddy discards client-supplied forwarding headers (no `trusted_proxies`).

The onion address is in `/var/lib/tor/anecdata/hostname`. Publish it on the site. Over the
onion service there is no client IP at any layer: the app sees every Tor connection as loopback,
so the per-address rate limit does not apply there — a shared ceiling of 300 submissions an hour
does (`app/src/lib/abuse.ts`). Build with the correct `PA_HOST`, or clearnet traffic through Caddy
is also seen as loopback and gets the same treatment.

Tor Browser at the **Safest** level disables SVG images, so release figures do not render there;
every figure has the same numbers as an HTML table directly beneath it, which does.

## Before the first real submission

- Delete any test rows: stop the service, remove `reports.db*`, start the service.
- Confirm `docs/SUBPROCESSORS.md` names the actual host, region, and backup location.
- Confirm the privacy statement carrying the no-re-identification commitment is live.
- Freeze `spec/taxonomy.v1.json` and `spec/RELEASE_SPEC.md`; hash and witness them.
