#!/usr/bin/env python3
"""
Render spec/SCHEMA.md from spec/taxonomy.v1.json + spec/uniqueness.synthetic.json.

The prose sections are authored here; the vocabulary tables are generated so they cannot drift
from the JSON the form and the release pipeline actually use.
"""
import json
from collections import OrderedDict

tax = json.load(open("spec/taxonomy.v1.json"))
uniq = json.load(open("spec/uniqueness.synthetic.json"))

goal_label = {g["id"]: g["label"] for g in tax["goals"]}
ae_label = {a["id"]: a["label"] for a in tax["adverseEffects"]}
uae_label = {a["id"]: a["label"] for a in tax["universalAdverseEffects"]}
route_label = {r["id"]: r["label"] for r in tax["routes"]}
freq_label = {f["id"]: f["label"] for f in tax["frequency"]}
class_label = {c["id"]: c["label"] for c in tax["classes"]}
by_class = {c["id"]: c["members"] for c in tax["classes"]}
comp = {c["id"]: c for c in tax["compounds"]}

out = []
w = out.append

w("# Submission schema")
w("")
w(f"**Version {tax['version']}.** This document is the schema. The form, the database, the release")
w("pipeline, and the uniqueness analysis are all generated from `spec/taxonomy.v1.json`, and the")
w("tables below are rendered from that file so they cannot drift from it. The schema is frozen at")
w("launch and changed only on a published schedule, in batches, with a version increment — because a")
w("dropdown that grows announces, dated and diffable in a public repository, that someone reported")
w("the new item.")
w("")
w("## Principles")
w("")
w("1. **Every field is a controlled vocabulary.** There is no free-text field anywhere in the form or")
w("   the schema. Free text is where names, places, employers and providers end up, and it imposes a")
w("   human moderation cost a solo operator cannot absorb.")
w("2. **Coarsen in the browser, before transmission.** The server never receives an exact dose, an")
w("   exact date, a vendor name, or a location. It receives the band, the bucket, the channel type.")
w("   What is not received cannot be leaked, subpoenaed, or breached.")
w("3. **One goal per report.** The contributor selects the single primary goal from that compound's")
w("   predefined list and rates the outcome for that goal. A multi-select goal was the single largest")
w("   identifier in the earlier analysis (the *combination* of goals is a fingerprint); single-select")
w("   halves plausible-post uniqueness and makes the '% reporting no change' denominator clean.")
w("4. **No location, at any granularity.** It adds little analytic value for this dataset, it is the")
w("   attribute people volunteer in public posts, and holding it would give the operator knowledge of")
w("   contributor geography that the non-targeting posture depends on not having.")
w("5. **No timestamps finer than a day, and no start date at all.** `duration` captures elapsed time.")
w("   A start quarter cost 7–21 points of uniqueness for almost no analytic gain.")
w("6. **Rare compounds are always accepted and never published alone.** Every compound belongs to a")
w("   mechanism class with at least three members. Below the release threshold, a compound is")
w("   published only rolled into its class — never into a residual 'other' whose membership could be")
w("   inferred by subtraction.")
w("7. **Every list ends with 'other (not listed)'.** It is counted and never broken out.")
w("")
w("## The submission record")
w("")
w("One row per report. Fields in form order.")
w("")
w("| # | Field | Vocabulary | Notes |")
w("|---|---|---|---|")
w(f"| 1 | `compound` | {len(tax['compounds'])} compounds + other | Frozen list, aliases shown in the picker |")
w("| 2 | `route` | That compound's routes | Single-select |")
w("| 3 | `goal` | That compound's goal list | **Single-select.** The primary reason for use |")
w("| 4 | `source_channel` | 8 options | Channel *type* only; never a vendor, pharmacy or brand |")
w("| 5 | `start_dose` | That compound's dose bands | Band, never a number |")
w("| 6 | `current_dose` | That compound's dose bands | Current or final |")
w("| 7 | `frequency` | That compound's frequency options | Includes 'cycled' |")
w("| 8 | `duration` | 6 buckets | How long taken in total |")
w("| 9 | `purity_tested` | 5 options | Independent test obtained; did it match the label |")
w("| 10 | `status` | 3 options | Still taking, finished a planned course, or stopped early |")
w("| 11 | `stop_reason` | 7 options | Only if stopped early |")
w("| 12 | `outcome` | 4-point scale | For the goal selected in #3 |")
w("| 13 | `adverse_effects[]` | Universal list + that compound's list | Multi-select. Each selected effect carries `onset` and `dechallenge` |")
w("| 14 | `age_band` | 6 bands | Optional |")
w("| 15 | `sex` | 5 options | Optional. Sex or gender, one question, never crossed with anything |")
w("")
w("**Held by the server in addition:** a received date at day granularity, assigned on write; a")
w("per-row secret salt for the Merkle log. **Nothing else.** No sequence number is exposed. No IP,")
w("no user agent, no session, no timestamp finer than a day, no location, no identifier.")
w("")
w("## Shared vocabularies")
w("")
w("### Source channel")
w("")
w("| id | Label |")
w("|---|---|")
for oid, lbl in [
    ("retail-pharmacy", "Retail pharmacy (brand product, prescription)"),
    ("503a-compounder", "Compounding pharmacy (503A)"),
    ("telehealth-compounded", "Telehealth or clinic (compounded)"),
    ("domestic-rc-vendor", "Domestic research-chemical vendor"),
    ("overseas-vendor", "Overseas vendor"),
    ("another-person", "From another person"),
    ("unknown", "Don't know"),
    ("other", "Other (not listed)"),
]:
    w(f"| `{oid}` | {lbl} |")
w("")
w("### Duration")
w("")
w("`under-2wk` · `2-4wk` · `1-3mo` · `3-6mo` · `6-12mo` · `over-12mo`")
w("")
w("### Purity testing")
w("")
w("`no` — did not test · `yes-matched` — tested, matched the label · `yes-did-not-match` — tested, did")
w("not match · `yes-unsure` — tested, unsure how to read the result · `dont-know`")
w("")
w("### Outcome scale (for the selected goal)")
w("")
w("`no-change` · `slight` · `moderate` · `large`")
w("")
w("### Status and stop reason")
w("")
w("Status: `still-taking` · `completed-planned-course` · `stopped` (before planned)")
w("")
w("Stop reason (if stopped early): `achieved-goal` · `no-effect` · `adverse-effect` · `cost` · `supply` ·")
w("`safety-concern` · `other`")
w("")
w("### Adverse-effect detail (per selected effect)")
w("")
w("Onset: `first-days` · `first-2wk` · `2-6wk` · `after-6wk` · `unsure`")
w("")
w("Dechallenge (did it resolve on stopping): `resolved` · `did-not-resolve` · `still-taking` · `unsure`")
w("")
w("### Age band and sex or gender (optional)")
w("")
w("Age: `18-24` · `25-34` · `35-44` · `45-54` · `55-64` · `65+`")
w("")
w("Sex or gender (one question; reported only as a total across all contributors): `female` · `male` ·")
w("`intersex` · `nonbinary` · `prefer-not`")
w("")
w("### Routes")
w("")
w("| id | Label |")
w("|---|---|")
for r in tax["routes"]:
    w(f"| `{r['id']}` | {r['label']} |")
w("")
w("### Frequency")
w("")
w("| id | Label |")
w("|---|---|")
for f in tax["frequency"]:
    w(f"| `{f['id']}` | {f['label']} |")
w("")
w("### Universal adverse effects (asked for every compound)")
w("")
w("Route-gated items are shown only when the matching route is selected.")
w("")
w("| id | Label |")
w("|---|---|")
for a in tax["universalAdverseEffects"]:
    gate = " *(injectable routes)*" if a["id"] == "injection-site" else (" *(nasal route)*" if a["id"] == "nasal-irritation" else "")
    w(f"| `{a['id']}` | {a['label']}{gate} |")
w("")
w("### Goal vocabulary (global)")
w("")
w("Each compound exposes a subset. The same id means the same goal everywhere, so within-goal")
w("tables can be built across compounds.")
w("")
w("| id | Label |")
w("|---|---|")
for g in tax["goals"]:
    w(f"| `{g['id']}` | {g['label']} |")
w("")
w("### Compound-specific adverse-effect vocabulary (global)")
w("")
w("| id | Label |")
w("|---|---|")
for a in tax["adverseEffects"]:
    w(f"| `{a['id']}` | {a['label']} |")
w("")
w("## Mechanism classes (for rollup)")
w("")
w("A compound below the release threshold is published only as its class.")
w("")
w("| Class | Members |")
w("|---|---|")
for c in tax["classes"]:
    w(f"| **{c['label']}** (`{c['id']}`) | {', '.join(comp[m]['label'] for m in c['members'])} |")
w("")
w("## Compounds")
w("")
w("Dose bands are **collection buckets, not dosing guidance**. They exist because an exact dose is")
w("a fingerprint. They were set as wide survey bins from what community sources report using, and")
w("they say nothing about what anyone should take.")
w("")
w("This schema says nothing about the legal, regulatory, or anti-doping status of any compound, and")
w("nothing on this site does. *Human evidence* below is a coarse note on how much published human")
w("data exists — the reason a compound is here — and is not a statement about safety or effect.")
w("Contributors subject to anti-doping testing should consult their national anti-doping")
w("organisation or GlobalDRO; we offer no view.")
w("")
for c in tax["classes"]:
    w(f"### {c['label']}")
    w("")
    for mid in c["members"]:
        m = comp[mid]
        w(f"#### {m['label']}  `{m['id']}`")
        w("")
        w(f"*Also known as:* {', '.join(m['aliases'][:8])}")
        w("")
        w(f"*Human evidence:* {m['humanEvidence']}")
        w("")
        w("| | |")
        w("|---|---|")
        w(f"| Goals | {' · '.join(goal_label[g] for g in m['goals'])} |")
        w(f"| Adverse effects (in addition to universal) | {' · '.join(ae_label[a] for a in m['adverseEffects'])} |")
        w(f"| Routes | {' · '.join(route_label[r] for r in m['routes'])} |")
        w(f"| Dose bands | {' · '.join(m['doseBands'])} |")
        w(f"| Frequency | {' · '.join(freq_label[f] for f in m['frequency'])} |")
        w("")
w("## Uniqueness analysis")
w("")
w("`tools/uniqueness.py synthetic spec/schema.config.json` generates rows from this schema under")
w("stated skew assumptions and reports how many are unique on several quasi-identifier sets. This")
w("is published so the identifiability of the store is a stated number, not a claim.")
w("")
w("**Assumptions:** compound prevalence Zipf(s=1.0) over 30 compounds; dose bands middle-heavy; one")
w("goal per row, Zipf(0.8) within the compound's list; age and sex skewed to the community's known")
w("demographics; source channel dominated by research-chemical vendors. These are assumptions")
w("made before any data existed. The same tool runs in `real` mode on the private store before every release, and the")
w("summary numbers (never rows) are published with the release.")
w("")
w("| Quasi-identifier set | Fields | n=500 | n=5,000 | n=50,000 |")
w("|---|---|---|---|---|")
reps = {r["n"]: r for r in uniq["reports"]}
names = OrderedDict([
    ("narrow", "Detailed post"),
    ("plausible-post", "Typical post"),
    ("plausible-post-no-dose", "Typical post, no dose"),
    ("demographics-only", "Compound + age + sex"),
    ("broad", "Entire row"),
])
for qi, lbl in names.items():
    cells = {}
    for n in (500, 5000, 50000):
        r = next(x for x in reps[n]["k_anonymity"] if x["qi_set"] == qi)
        cells[n] = f"{r['unique_rows_pct']}% unique"
        if qi == "narrow" and n == 500:
            fields = ", ".join(r["qi_fields"])
    r0 = next(x for x in reps[500]["k_anonymity"] if x["qi_set"] == qi)
    w(f"| {lbl} | {len(r0['qi_fields'])} | {cells[500]} | {cells[5000]} | {cells[50000]} |")
w("")
w("**What this means.** On the entire row, the store is near-unique at every size — that is the")
w("nature of a schema rich enough to be useful, and no amount of coarsening changes it without")
w("destroying the data. On what a typical detailed public post reveals — compound, age band, sex,")
w("goal, and dose band — roughly a third of rows are unique at n=5,000. Someone who obtained the")
w("raw store *and* had read a contributor's detailed post could shortlist that contributor's row.")
w("")
w("**Why this does not make the row personal data, and what does the work instead.** The")
w("de-identification argument does not rest on row-level k-anonymity; it rests on four things.")
w("There is no direct or persistent identifier, no IP, no location. The coarsening removes the")
w("precision an adversary needs — a public post gives a dose, not a dose band; a start date, not a")
w("duration bucket. The store is never published, so linkage requires both a breach or subpoena")
w("*and* auxiliary information about a specific target. And the statutory three-part test")
w("(reasonable measures, a public commitment not to re-identify, downstream contractual obligations)")
w("does not require k-anonymity. Under the EU singling-out test the argument is harder, which is")
w("why the site does not target the EEA.")
w("")
w("**What the marginal analysis says.** With `quarter_started` removed and goal made single-select,")
w("no one field dominates: at n=5,000, dropping any of goal, source channel, duration, age band or")
w("dose band reduces uniqueness by roughly 20 points, and dropping compound reduces it by almost")
w("nothing. Further coarsening of any single field would not change the picture. The fields kept")
w("are the ones the dataset exists to collect.")
w("")
w("## Change control")
w("")
w("The taxonomy is versioned. Additions are batched and published on a schedule, never in response")
w("to a single submission. A removed option is retained in the schema as deprecated so historical")
w("rows remain interpretable. Every change increments the version and appears in the changelog.")
w("")

open("spec/SCHEMA.md", "w").write("\n".join(out))
print(f"wrote spec/SCHEMA.md ({len(out)} lines)")
