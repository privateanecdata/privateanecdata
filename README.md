# privateanecdata.org (working name)

A structured, identifier-free census of gray-market peptide use, published as aggregate
statistics under a release specification fixed before any data was collected.

**Status: pre-launch. No data has been collected. Nothing here is live.**

## What this is

People are using compounds — BPC-157, TB-500, KPV, semax, epitalon, and roughly four dozen
others — for which there is little or no human data. FDA is making compounding determinations
about these exact substances in an evidence vacuum. The only information that exists is scattered
across forum posts, and every site that claims to aggregate it turns out, on inspection, to be
running on seed data, scraped rows, or numbers its own endpoints don't support.

This project collects one-time structured reports — no account, no email, no key, no free text,
no location, coarsened in the browser before anything is sent — and publishes only the
statistics enumerated in a pre-registered specification. Every submission is committed to a
public log so the count is checkable. Every release is witnessed in a transparency log so it
cannot be quietly revised.

**Privacy-preserving is the precondition. Independently verifiable is the point.**

## The documents are the product

| Document | What it is |
|---|---|
| [`spec/SCHEMA.md`](spec/SCHEMA.md) | The frozen schema: 50 compounds, every controlled vocabulary, six mechanism classes for rollup, and the published uniqueness analysis. Rendered from `spec/taxonomy.v1.json`. |
| [`spec/RELEASE_SPEC.md`](spec/RELEASE_SPEC.md) | Every table that will ever be published and the threshold governing each. Fixed and witnessed before the first row. |
| [`docs/THREAT_MODEL.md`](docs/THREAT_MODEL.md) | What the system enforces, by threat, written as a specification rather than a risk register. |
| [`docs/WHAT-WE-CANNOT-PROTECT-YOU-FROM.md`](docs/WHAT-WE-CANNOT-PROTECT-YOU-FROM.md) | The limits, stated for contributors before they submit. |
| [`docs/ANALYSES-WE-WILL-NEVER-RUN.md`](docs/ANALYSES-WE-WILL-NEVER-RUN.md) | Rankings, comparisons, rates, causal language, individualized output — the list of refusals. |
| [`docs/LEGAL-PROCESS.md`](docs/LEGAL-PROCESS.md) | What is held, retention, and what a subpoena obtains. |
| [`docs/SUBPROCESSORS.md`](docs/SUBPROCESSORS.md) | The complete list of third parties. It has two entries. |
| [`docs/SHUTDOWN.md`](docs/SHUTDOWN.md) | Kill criterion, destruction protocol, and the commitment that the store is never transferred. |
| [`docs/HOW-TO-VERIFY.md`](docs/HOW-TO-VERIFY.md) | What each check on a release proves, how to run it, and what nothing can prove. |

## The app

`app/` is the site: Astro in server mode on the Node adapter, SQLite via better-sqlite3, no
client-side JavaScript at all.

```bash
cd app && npm install && npm run build && npm run start     # http://127.0.0.1:4321
```

- **Seven-screen form, no JavaScript.** Every screen POSTs to `/contribute` with the running
  answers in a hidden field; the server validates that screen against `spec/taxonomy.v1.json`
  and renders the next. The server holds nothing between screens. Only the confirm on the
  review screen writes, and it is the only request that redirects — so a refresh can never
  double-submit.
- **What the server stores:** the schema fields, a day-granularity received date, a random
  62-bit rowid (insertion order is not recoverable from the key), and a per-row secret salt.
  A Merkle leaf is appended in the same transaction. No sessions, no drafts, no logs.
- **Headers:** `Content-Security-Policy: default-src 'none'; style-src 'self'; …` with no
  `script-src` at all. Query strings on `/contribute` are rejected. No cookie is ever set.
- **Anti-abuse:** a honeypot field, and an in-memory rate limit keyed on a hash of the client
  address with an hourly-rotated salt that never touches disk.
- **Deploy:** `deploy/` has a Caddyfile with access logging off, a hardened systemd unit, and
  the Tor onion-service config.

## Tools

| Tool | Purpose |
|---|---|
| `tools/uniqueness.py` | The gate. Generates synthetic rows from the schema and reports k-anonymity on several quasi-identifier sets; runs in `real` mode on the private store before every release. |
| `tools/normalize_taxonomy.py` | Hand-maintained mapping from researched vocabulary to canonical ids. Produces `spec/taxonomy.v1.json`. |
| `tools/make_schema_config.py` | Derives the uniqueness config from the taxonomy. |
| `tools/render_schema_md.py` | Renders `SCHEMA.md` from the taxonomy so the tables cannot drift. |
| `tools/release.py` | The release pipeline. Verifies the store against its Merkle log, applies exclusions, computes every table under the tier rules, renders the figures with the caveats inside them, audits its own output for any count under the floor, and writes `release.json` with the hash of every file. Deterministic. |
| `tools/verify_release.py` | Anyone's check on a published release: file hashes, Merkle root and count, append-only continuity with the prior release, spec and schema hashes, signature, Rekor and OpenTimestamps. Operators add `--db` to check rows against the log. |
| `tools/detect.py` | Quality detector. Proposes exclusions (malformed, implausible, duplicate-pattern, coordinated) for a person to review; `apply` records the reviewed list. |
| `tools/witness.sh` | Signs `release.json` and submits its hash to Rekor and OpenTimestamps. |
| `tools/synth_store.py` | A synthetic store for testing the pipeline, written the way the app writes. Releases from it must carry `SYNTHETIC` in their name. |
| `tools/pa_store.py` | Read-only store access and a byte-exact mirror of the app's leaf and root computation, verified against rows the app wrote. |
| `tools/check_origin.sh` | Builds and starts the site, crawls every page, and fails if anything loads from another origin or any `<script>` exists. `npm test` in `app/`. The enforcement behind "one host." |
| `tools/tests/` | Unit tests for the Merkle mirror, suppression and complementary suppression, tier boundaries, Wilson intervals, the detector's contradiction rules, and an end-to-end synthetic release with tamper cases. `python3 -m unittest discover -s tools/tests`. |
| `tools/preflight.sh` | Everything above in one run: derived spec files in sync, tests, a synthetic release built and verified, the one-origin check. CI runs it on every push (`.github/workflows/check.yml`). |

```bash
python3 tools/normalize_taxonomy.py      # research json -> taxonomy.v1.json
python3 tools/make_schema_config.py      # taxonomy -> schema.config.json
python3 tools/uniqueness.py synthetic spec/schema.config.json --json spec/uniqueness.synthetic.json
python3 tools/render_schema_md.py        # -> spec/SCHEMA.md

python3 tools/synth_store.py /tmp/synth.db --n 3000            # a test store
python3 tools/release.py --db /tmp/synth.db --id 2026-Q4-SYNTHETIC --date 2026-12-31 --out releases/2026-Q4-SYNTHETIC
python3 tools/verify_release.py releases/2026-Q4-SYNTHETIC --spec spec/RELEASE_SPEC.md --taxonomy spec/taxonomy.v1.json --db /tmp/synth.db
```

The site serves whatever is under `releases/` at `/releases/<id>/` and lists it on `/data`.
[`docs/HOW-TO-VERIFY.md`](docs/HOW-TO-VERIFY.md) explains what each check proves.

## Before launch — in order

1. **Distribution gate.** One week of moderator outreach in r/Peptides and the compound-specific
   communities, and ~20 DMs to active posters. Zero code. A "no" from everyone redirects this to
   a published reference implementation rather than a live site.
2. **Name.** Trademark risk on the current name is low; the affiliation collision with
   Anecdata.org is the reason to change it. Shortlist in the plan. Register the finalist the same
   day.
3. **Verify the dose bands marked *(verify)* in SCHEMA.md** against community norms. They were
   set as wide survey bins and need a second look before the schema is frozen.
4. **Review the privacy statement and terms.** Drafts are at [`docs/PRIVACY.md`](docs/PRIVACY.md)
   and [`docs/TERMS.md`](docs/TERMS.md), rendered at `/docs/privacy` and `/docs/terms`. Not
   MHMDA-titled. The privacy statement carries the **public commitment not to attempt
   re-identification** — a statutory element of de-identification, which must be live before the
   first row — and leads the no-deletion explanation with "we cannot tell which report is yours."
   The terms carry the irrevocable no-disclosure covenant (§4, written to bind successors and
   insolvency), the no-promotion and no-re-identification conditions on published releases, and
   assent by conspicuous notice at the Submit button. Bracketed items are filled at formation.
   Decide the license line in §5 (README's TBDs). Then witness both: `tools/witness.sh all`.
5. **Form the single-member Oregon LLC** with a commercial registered agent. ~$225, ~3 business
   days. Then the EIN.
6. **Freeze the schema and the release spec**, hash both, submit to Rekor and OpenTimestamps,
   record in [`spec/WITNESS.md`](spec/WITNESS.md) (scaffold in place; `tools/witness.sh all
   spec/RELEASE_SPEC.md` does each one). Test on a throwaway file first — Rekor is permanent.
7. ~~Build the form.~~ ~~Build the release pipeline and verifier.~~ Both built and tested
   against synthetic stores (suppression, complementary suppression, tiering, tamper and deletion
   detection, append-only continuity, byte-identical re-runs). Remaining: generate the release
   signing key (`tools/witness.sh keygen`), publish `releases/pubkey.pem`, and do one dry run of
   `witness.sh` against a throwaway artifact before the first real release; the Tor Browser test
   at the Safest setting (Safest disables SVG, so every figure on a release page has the same
   numbers as an HTML table beneath it — check that path too).

## What is not in scope

Deletion after submission. Follow-ups. Accounts. Free text. Vendor names. Location. Differential
privacy. Rankings. An API. See the documents above for why each is excluded.

## License

Code: [TBD — MIT or Apache-2.0]. Documents: [TBD — CC BY 4.0]. Published releases: [TBD — CC0
with a no-re-identification use agreement].
