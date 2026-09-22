# Deploying

One US VPS. Caddy in front, the Node server on loopback, SQLite on local disk. No CDN, no WAF,
no third-party edge.

## Layout

```
/srv/private-anecdata/
  app/          the built app (this repo's app/ after `npm run build`)
  data/         reports.db and its WAL — owned by the service user, mode 0700
  releases/     published releases, written by tools/release.py — read-only to the service
```

## Steps

1. Create the service user: `useradd -r -s /usr/sbin/nologin anecdata`.
2. Copy `app/` (with `node_modules` and `dist/`) to `/srv/private-anecdata/app`.
3. `mkdir -p /srv/private-anecdata/data && chown anecdata:anecdata /srv/private-anecdata/data && chmod 700 /srv/private-anecdata/data`.
4. Install `private-anecdata.service` to `/etc/systemd/system/`, `systemctl enable --now private-anecdata`.
5. Install Caddy. Put `Caddyfile` at `/etc/caddy/Caddyfile` with the real hostname.
6. **TLS session resumption — open item.** The threat model says session tickets are disabled on
   the submission origin. Caddy rotates ticket keys automatically and does not persist them, but
   whether tickets can be turned off per-site in the current Caddy release has not been verified.
   Verify against the Caddy docs for the installed version before publishing that claim; until
   then, state the rotation behaviour rather than "disabled."
7. `systemctl enable --now caddy`.
8. Full-disk encryption on the VPS volume. Backups of `data/` encrypted with a key that does
   not live on the host; retention stated in `docs/LEGAL-PROCESS.md`.
9. `mkdir -p /srv/private-anecdata/releases`. The service reads it (`PA_RELEASES_DIR`) and
   serves it under `/releases/`; it never writes there.

## Making a release

Quarterly, by hand, on the host, as a user other than the service user:

```
cd /srv/private-anecdata/repo                                  # a checkout of this repository
python3 tools/detect.py scan --db ../data/reports.db --out /root/candidates.json
#   review /root/candidates.json — remove anything you do not agree with — then:
python3 tools/detect.py apply --db ../data/reports.db /root/candidates.json --date YYYY-MM-DD
rm /root/candidates.json
python3 tools/release.py --db ../data/reports.db --id YYYY-QN --date YYYY-MM-DD \
    --out ../releases/YYYY-QN --prior ../releases/<previous>
python3 tools/verify_release.py ../releases/YYYY-QN --prior ../releases/<previous> \
    --spec spec/RELEASE_SPEC.md --taxonomy spec/taxonomy.v1.json --db ../data/reports.db
#   read every table against RELEASE_SPEC.md before going further
tools/witness.sh all ../releases/YYYY-QN                       # sign, Rekor, OpenTimestamps
git add releases/YYYY-QN && git commit -S -m "release YYYY-QN" && git tag -s release/YYYY-QN
tools/witness.sh upgrade ../releases/YYYY-QN                   # a day later, then commit the upgraded .ots
```

`detect.py apply` is the only write to the store that is not the form; it adds rows to the
`exclusions` table and touches nothing else. The signing key lives in `~/.config/private-anecdata/`
of the releasing user, mode 0600, never on the service user and never in the repository.

## What is and is not logged

- **Caddy:** `log { output discard }` — no access log. Process logs to journald contain startup,
  TLS, and error lines only.
- **App:** writes nothing per request. The only startup line is the adapter's "listening on".
- **journald:** contains nothing request-level. Consider `Storage=volatile` in
  `/etc/systemd/journald.conf` so even process logs do not persist across reboots.
- **Kernel / netfilter:** do not enable connection logging.
- **Rate limiter:** Caddy forwards the client address; the app hashes it with an hourly
  in-memory salt (`src/lib/abuse.ts`) and keeps a count for the hour. Nothing is written to disk
  and nothing survives a restart. Set `PA_HOST` so Astro trusts the forwarded header.

## Regional block (optional, off by default)

The plan allows declining clearnet connections from the EEA, UK and Switzerland as evidence of
non-targeting. It is not built into this configuration. If enabled, do it in Caddy with a GeoIP
module (for example `caddy-maxmind-geolocation` against a locally held MaxMind database) as an
in-memory lookup that returns a plain 403 and logs nothing — then un-bracket the two sentences
about it in `docs/PRIVACY.md`. The onion service cannot be region-blocked and the privacy
statement should not claim otherwise. Until enabled, leave the bracketed sentences out of the
published statement.

## Tor onion service

Install `tor`; in `/etc/tor/torrc`:

```
HiddenServiceDir /var/lib/tor/anecdata/
HiddenServicePort 80 127.0.0.1:4321
```

The onion address is in `/var/lib/tor/anecdata/hostname`. Publish it on the site. Over the
onion service there is no client IP at any layer: the app sees every Tor connection as loopback,
so the per-address rate limit does not apply there — a shared ceiling of 300 submissions an hour
does (`app/src/lib/abuse.ts`). Set `PA_HOST` correctly, or clearnet traffic through Caddy is also
seen as loopback and gets the same treatment.

Tor Browser at the **Safest** level disables SVG images, so release figures do not render there;
every figure has the same numbers as an HTML table directly beneath it, which does.

## Before the first real submission

- Delete any test rows: stop the service, remove `reports.db*`, start the service.
- Confirm `docs/SUBPROCESSORS.md` names the actual host, region, and backup location.
- Confirm the privacy statement carrying the no-re-identification commitment is live.
- Freeze `spec/taxonomy.v1.json` and `spec/RELEASE_SPEC.md`; hash and witness them.
