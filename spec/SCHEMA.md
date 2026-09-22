# Submission schema

**Version 1.0.** This document is the schema. The form, the database, the release
pipeline, and the uniqueness analysis are all generated from `spec/taxonomy.v1.json`, and the
tables below are rendered from that file so they cannot drift from it. The schema is frozen at
launch and changed only on a published schedule, in batches, with a version increment — because a
dropdown that grows announces, dated and diffable in a public repository, that someone reported
the new item.

## Principles

1. **Every field is a controlled vocabulary.** There is no free-text field anywhere in the form or
   the schema. Free text is where names, places, employers and providers end up, and it imposes a
   human moderation cost a solo operator cannot absorb.
2. **Coarsen in the browser, before transmission.** The server never receives an exact dose, an
   exact date, a vendor name, or a location. It receives the band, the bucket, the channel type.
   What is not received cannot be leaked, subpoenaed, or breached.
3. **One goal per report.** The contributor selects the single primary goal from that compound's
   predefined list and rates the outcome for that goal. A multi-select goal was the single largest
   identifier in the earlier analysis (the *combination* of goals is a fingerprint); single-select
   halves plausible-post uniqueness and makes the '% reporting no change' denominator clean.
4. **No location, at any granularity.** It adds little analytic value for this dataset, it is the
   attribute people volunteer in public posts, and holding it would give the operator knowledge of
   contributor geography that the non-targeting posture depends on not having.
5. **No timestamps finer than a day, and no start date at all.** `duration` captures elapsed time.
   A start quarter cost 7–21 points of uniqueness for almost no analytic gain.
6. **Rare compounds are always accepted and never published alone.** Every compound belongs to a
   mechanism class with at least three members. Below the release threshold, a compound is
   published only rolled into its class — never into a residual 'other' whose membership could be
   inferred by subtraction.
7. **Every list ends with 'other (not listed)'.** It is counted and never broken out.

## The submission record

One row per report. Fields in form order.

| # | Field | Vocabulary | Notes |
|---|---|---|---|
| 1 | `compound` | 50 compounds + other | Frozen list, aliases shown in the picker |
| 2 | `route` | That compound's routes | Single-select |
| 3 | `goal` | That compound's goal list | **Single-select.** The primary reason for use |
| 4 | `source_channel` | 8 options | Channel *type* only; never a vendor, pharmacy or brand |
| 5 | `start_dose` | That compound's dose bands | Band, never a number |
| 6 | `current_dose` | That compound's dose bands | Current or final |
| 7 | `frequency` | That compound's frequency options | Includes 'cycled' |
| 8 | `duration` | 6 buckets | How long taken in total |
| 9 | `purity_tested` | 5 options | Independent test obtained; did it match the label |
| 10 | `status` | 3 options | Still taking, finished a planned course, or stopped early |
| 11 | `stop_reason` | 7 options | Only if stopped early |
| 12 | `outcome` | 4-point scale | For the goal selected in #3 |
| 13 | `adverse_effects[]` | Universal list + that compound's list | Multi-select. Each selected effect carries `onset` and `dechallenge` |
| 14 | `age_band` | 6 bands | Optional |
| 15 | `sex` | 5 options | Optional. Sex or gender, one question, never crossed with anything |

**Held by the server in addition:** a received date at day granularity, assigned on write; a
per-row secret salt for the Merkle log. **Nothing else.** No sequence number is exposed. No IP,
no user agent, no session, no timestamp finer than a day, no location, no identifier.

## Shared vocabularies

### Source channel

| id | Label |
|---|---|
| `retail-pharmacy` | Retail pharmacy (brand product, prescription) |
| `503a-compounder` | Compounding pharmacy (503A) |
| `telehealth-compounded` | Telehealth or clinic (compounded) |
| `domestic-rc-vendor` | Domestic research-chemical vendor |
| `overseas-vendor` | Overseas vendor |
| `another-person` | From another person |
| `unknown` | Don't know |
| `other` | Other (not listed) |

### Duration

`under-2wk` · `2-4wk` · `1-3mo` · `3-6mo` · `6-12mo` · `over-12mo`

### Purity testing

`no` — did not test · `yes-matched` — tested, matched the label · `yes-did-not-match` — tested, did
not match · `yes-unsure` — tested, unsure how to read the result · `dont-know`

### Outcome scale (for the selected goal)

`no-change` · `slight` · `moderate` · `large`

### Status and stop reason

Status: `still-taking` · `completed-planned-course` · `stopped` (before planned)

Stop reason (if stopped early): `achieved-goal` · `no-effect` · `adverse-effect` · `cost` · `supply` ·
`safety-concern` · `other`

### Adverse-effect detail (per selected effect)

Onset: `first-days` · `first-2wk` · `2-6wk` · `after-6wk` · `unsure`

Dechallenge (did it resolve on stopping): `resolved` · `did-not-resolve` · `still-taking` · `unsure`

### Age band and sex or gender (optional)

Age: `18-24` · `25-34` · `35-44` · `45-54` · `55-64` · `65+`

Sex or gender (one question; reported only as a total across all contributors): `female` · `male` ·
`intersex` · `nonbinary` · `prefer-not`

### Routes

| id | Label |
|---|---|
| `subcutaneous` | Subcutaneous injection |
| `intramuscular` | Intramuscular injection |
| `intranasal` | Nasal spray / drops |
| `oral` | Oral / sublingual / troche |
| `topical` | Topical / transdermal |
| `intravenous` | Intravenous (clinic) |

### Frequency

| id | Label |
|---|---|
| `multiple-daily` | More than once a day |
| `daily` | Once a day |
| `5-on-2-off` | 5 days on / 2 days off |
| `every-other-day` | Every other day |
| `2-3-weekly` | 2–3 times a week |
| `weekly` | About once a week |
| `less-than-weekly` | Less than weekly |
| `as-needed` | As needed / on demand |
| `cycled` | In cycles (weeks on, weeks off) |

### Universal adverse effects (asked for every compound)

Route-gated items are shown only when the matching route is selected.

| id | Label |
|---|---|
| `headache` | Headache |
| `nausea` | Nausea |
| `vomiting` | Vomiting |
| `dizziness` | Dizziness or lightheadedness |
| `fatigue` | Fatigue / low energy |
| `insomnia` | Trouble sleeping |
| `vivid-dreams` | Vivid dreams |
| `flushing` | Flushing or feeling warm |
| `anxiety-jittery` | Anxiety, restlessness or feeling wired |
| `low-mood` | Low mood or irritability |
| `appetite-change` | Appetite change |
| `injection-site` | Injection-site reaction (redness, itching, lump, bruising) *(injectable routes)* |
| `nasal-irritation` | Nasal irritation, burning or sneezing *(nasal route)* |
| `tolerance` | Effect faded with repeated use |
| `no-effect` | No noticeable effect at all |

### Goal vocabulary (global)

Each compound exposes a subset. The same id means the same goal everywhere, so within-goal
tables can be built across compounds.

| id | Label |
|---|---|
| `fat-loss` | Fat loss / weight loss |
| `visceral-fat` | Reducing belly / visceral fat specifically |
| `recomp` | Losing fat while keeping or building muscle |
| `plateau` | Breaking a weight-loss plateau |
| `weight-maintenance` | Maintaining weight after a prior loss (low-dose / microdose) |
| `appetite-control` | Appetite control / quieting food noise |
| `appetite-increase` | Increasing appetite (bulking) |
| `glp1-stack` | Adding to a GLP-1 for extra effect |
| `muscle-gain` | Muscle gain |
| `training-recovery` | Faster recovery from training |
| `endurance` | More endurance / exercise capacity |
| `athletic-performance` | Athletic performance |
| `injury-healing` | Healing a tendon, ligament, muscle or joint injury |
| `joint-pain` | Joint or cartilage pain relief |
| `wound-scar` | Healing wounds, scars, acne marks or stretch marks |
| `gut` | Gut issues (IBS, ulcers, leaky gut, inflammation) |
| `gut-infection` | Gut infection or dysbiosis (SIBO, candida) |
| `chronic-injury` | An old or chronic injury that never fully healed |
| `post-surgery` | Recovery after surgery |
| `mobility` | Flexibility, mobility or stiffness |
| `chronic-pain` | Chronic pain |
| `nerve-pain` | Nerve pain or neuropathy |
| `skin-condition` | Skin condition (eczema, psoriasis, rosacea, acne) |
| `allergy-mcas` | Allergies, histamine or mast-cell issues |
| `autoimmune` | Autoimmune flares or body-wide inflammation |
| `sinus-respiratory` | Sinus or respiratory issues |
| `infection` | Chronic or stealth infection (Lyme, mold, biofilm) |
| `blood-sugar` | Blood sugar / insulin resistance / A1c |
| `pcos` | PCOS-related weight or insulin issues |
| `liver-fat` | Reducing liver fat |
| `cardio-kidney` | Heart or kidney protection |
| `lipids` | Cholesterol or other blood markers |
| `cravings` | Cutting alcohol, nicotine or other cravings |
| `withdrawal` | Easing withdrawal or tapering off a substance |
| `deeper-sleep` | Deeper, more restorative sleep |
| `fall-asleep` | Falling asleep faster |
| `focus` | Sharper focus and concentration |
| `memory` | Better memory and learning |
| `brain-fog` | Less brain fog / mental fatigue |
| `cognitive-decline` | Slowing memory loss or cognitive decline |
| `brain-injury` | Recovery after concussion, head injury or stroke |
| `neuroprotection` | Long-term brain health |
| `motivation` | More motivation and drive |
| `verbal-creativity` | Verbal fluency or creativity |
| `mood` | Better mood / lifting depression |
| `anxiety` | Less anxiety or stress |
| `social-ease` | Feeling calmer or more at ease socially |
| `energy` | More daily energy, less fatigue |
| `longevity` | General longevity / anti-aging |
| `immune` | Immune support / fewer infections |
| `long-covid` | Long COVID or chronic fatigue symptoms |
| `bone-density` | Bone density |
| `skin-aging` | Skin appearance / fine lines / anti-aging look |
| `hair` | Hair regrowth or thicker hair |
| `skin-tone` | More even skin tone |
| `tan` | Darker tan with less sun exposure |
| `sun-tolerance` | Tanning without burning / sun sensitivity |
| `libido` | Stronger sexual desire / libido |
| `erections` | Firmer or more reliable erections |
| `orgasm` | More intense arousal or orgasm |
| `ed-adjunct` | Add-on when ED medication is not enough |
| `testosterone` | Higher natural testosterone |
| `pct` | Restoring hormone function after a cycle or TRT |
| `fertility` | Fertility |
| `bonding` | Closer bonding or intimacy with a partner |
| `igf1` | Raising IGF-1 / GH on bloodwork |
| `annual-reset` | Periodic 'reset' course |
| `trt-support` | Keeping testicular function or fertility while on TRT |
| `glp1-alternative` | Alternative to weekly GLP-1 injections (oral / daily / cheaper) |
| `skin-brightening` | Skin brightening or lightening |
| `detox-liver` | Liver support / 'detox' |
| `hangover` | Hangover or post-drinking recovery |
| `cancer-adjunct` | Adjunct during cancer treatment |
| `hepatitis` | Hepatitis B or C |
| `eye-health` | Eye health |

### Compound-specific adverse-effect vocabulary (global)

| id | Label |
|---|---|
| `constipation` | Constipation |
| `diarrhea` | Diarrhea or loose stools |
| `reflux-bloating` | Acid reflux, bloating, burping or sulfur burps |
| `stomach-pain` | Stomach pain or cramping |
| `early-fullness` | Getting full very fast / eating too little |
| `gallbladder` | Gallbladder pain / gallstones |
| `pancreatitis-scare` | Severe stomach pain (pancreatitis scare) |
| `hypoglycemia` | Low blood sugar episodes (shaky, sweaty, weak) |
| `high-blood-sugar` | Elevated fasting blood sugar or insulin resistance on labs |
| `hunger` | Intense hunger or rebound cravings |
| `unwanted-weight-gain` | Unwanted weight gain |
| `water-retention` | Water retention, bloating or puffy face/hands |
| `joint-pain` | Joint pain or stiffness |
| `carpal-tunnel` | Tingling or numb hands / fingers |
| `swollen-extremities` | Swollen ankles or feet |
| `skin-tags-moles` | New skin tags or moles |
| `low-thyroid` | Low-thyroid symptoms |
| `muscle-cramps` | Muscle cramps or aches |
| `palpitations` | Racing heart, palpitations or higher resting heart rate |
| `blood-pressure` | Blood pressure changes |
| `chest-tightness` | Chest tightness or pressure |
| `brain-fog` | Brain fog or mental fatigue |
| `drowsiness` | Drowsiness or feeling flat / too calm |
| `grogginess` | Next-day grogginess or hangover feeling |
| `paradoxical` | Opposite of intended effect (e.g. more anxious, worse sleep) |
| `emotional` | Feeling weepy or emotionally raw |
| `agitation` | Agitation or feeling overstimulated |
| `hair-shedding` | Hair shedding |
| `moles-freckles` | New or darkening moles / freckles |
| `uneven-darkening` | Uneven skin darkening |
| `skin-irritation` | Skin irritation, rash, hives or breakouts |
| `skin-staining` | Blue-green staining or residue on skin |
| `dysesthesia` | Skin tingling, burning or sunburn-like sensitivity |
| `hyperpigmentation` | Skin, gum or mole darkening |
| `injury-worse` | Pain or inflammation got worse at the injury |
| `flu-like` | Flu-like or achy feeling for a day or two |
| `condition-flare` | Flare-up of the condition being treated |
| `herx` | 'Herx' / die-off reaction (fatigue, aches, chills) |
| `prolactin` | Low libido or nipple tenderness |
| `sweating` | Sweating |
| `skin-lightening` | Unwanted skin lightening |
| `dry-mouth` | Dry mouth |
| `facial-volume-loss` | Facial volume loss or loose skin |
| `acne` | Acne or oily skin |
| `erections-unwanted` | Unwanted or prolonged erections |
| `mood-swings` | Mood swings |
| `muscle-loss` | Muscle loss or weakness |
| `alcohol-sensitivity` | Alcohol hitting harder |
| `taste-changes` | Taste changes |
| `cramping-women` | Cramping (women) |
| `dyspnea-rare` | Trouble swallowing (rare) |
| `injection-pain-severe` | Severe stinging or pain at the injection site |

## Mechanism classes (for rollup)

A compound below the release threshold is published only as its class.

| Class | Members |
|---|---|
| **GLP-1 / incretin agonists** (`incretin`) | Retatrutide, Tirzepatide, Semaglutide, Cagrilintide, Mazdutide, Survodutide, Liraglutide |
| **Growth hormone axis** (`gh-secretagogue`) | CJC-1295 (no DAC) / ipamorelin blend, Ipamorelin, Tesamorelin, MK-677 (ibutamoren), Somatropin (HGH), CJC-1295 without DAC (Mod GRF 1-29), Sermorelin, CJC-1295 with DAC, GHRP-6, GHRP-2 (pralmorelin), Hexarelin |
| **Tissue repair / healing** (`tissue-repair`) | GHK-Cu, BPC-157, TB-500, BPC-157 + TB-500 blend (Wolverine stack), KPV, LL-37, ARA-290 (cibinetide) |
| **Nootropic / mood / sleep** (`neuro`) | Oxytocin (intranasal), DSIP (delta sleep-inducing peptide), Semax, Selank, Cerebrolysin, Dihexa, P21 (P021), Pinealon |
| **Metabolic / longevity** (`metabolic`) | AOD-9604, NAD+ (injectable), MOTS-c, Epitalon, 5-amino-1MQ, Glutathione (injectable), Thymosin alpha-1, Tesofensine, SS-31 (elamipretide), Humanin, SLU-PP-332, FOXO4-DRI |
| **Sexual function / hormonal** (`sexual-hormonal`) | PT-141 (bremelanotide), Melanotan II, Kisspeptin-10, Melanotan I (afamelanotide), Gonadorelin |

## Compounds

Dose bands are **collection buckets, not dosing guidance**. They exist because an exact dose is
a fingerprint. They were set as wide survey bins from what community sources report using, and
they say nothing about what anyone should take.

This schema says nothing about the legal, regulatory, or anti-doping status of any compound, and
nothing on this site does. *Human evidence* below is a coarse note on how much published human
data exists — the reason a compound is here — and is not a statement about safety or effect.
Contributors subject to anti-doping testing should consult their national anti-doping
organisation or GlobalDRO; we offer no view.

### GLP-1 / incretin agonists

#### Retatrutide  `retatrutide`

*Also known as:* reta, Reta, retatrutide, LY3437943, GLP-3, triple G, tri-agonist, triple agonist

*Human evidence:* large-rcts

| | |
|---|---|
| Goals | Fat loss / weight loss · Breaking a weight-loss plateau · Losing fat while keeping or building muscle · Appetite control / quieting food noise · Cutting alcohol, nicotine or other cravings · More endurance / exercise capacity · Blood sugar / insulin resistance / A1c · Joint or cartilage pain relief |
| Adverse effects (in addition to universal) | Constipation · Diarrhea or loose stools · Acid reflux, bloating, burping or sulfur burps · Racing heart, palpitations or higher resting heart rate · Skin tingling, burning or sunburn-like sensitivity · Intense hunger or rebound cravings · Hair shedding · Muscle loss or weakness · Next-day grogginess or hangover feeling |
| Routes | Subcutaneous injection |
| Dose bands | under 1 mg/week · 1 to under 2 mg/week · 2 to under 4 mg/week · 4 to under 6 mg/week · 6 mg/week or more |
| Frequency | About once a week · More than once a day · Less than weekly · Once a day · In cycles (weeks on, weeks off) |

#### Tirzepatide  `tirzepatide`

*Also known as:* tirz, Tirz, tirzepatide, Mounjaro, Zepbound, LY3298176, GIP/GLP-1, compounded tirz

*Human evidence:* large-rcts

| | |
|---|---|
| Goals | Fat loss / weight loss · Appetite control / quieting food noise · Blood sugar / insulin resistance / A1c · PCOS-related weight or insulin issues · Cutting alcohol, nicotine or other cravings · Maintaining weight after a prior loss (low-dose / microdose) · Joint or cartilage pain relief |
| Adverse effects (in addition to universal) | Constipation · Diarrhea or loose stools · Acid reflux, bloating, burping or sulfur burps · Hair shedding · Low blood sugar episodes (shaky, sweaty, weak) · Gallbladder pain / gallstones · Muscle loss or weakness |
| Routes | Subcutaneous injection · Oral / sublingual / troche |
| Dose bands | under 2.5 mg/week · 2.5 to under 5 mg/week · 5 to under 7.5 mg/week · 7.5 to under 10 mg/week · 10 mg/week or more |
| Frequency | About once a week · More than once a day · Less than weekly · Once a day · In cycles (weeks on, weeks off) |

#### Semaglutide  `semaglutide`

*Also known as:* sema, Sema, semaglutide, Ozempic, Wegovy, Rybelsus, compounded sema, gray sema

*Human evidence:* large-rcts

| | |
|---|---|
| Goals | Fat loss / weight loss · Appetite control / quieting food noise · Blood sugar / insulin resistance / A1c · Cutting alcohol, nicotine or other cravings · Maintaining weight after a prior loss (low-dose / microdose) · PCOS-related weight or insulin issues · Heart or kidney protection |
| Adverse effects (in addition to universal) | Constipation · Diarrhea or loose stools · Acid reflux, bloating, burping or sulfur burps · Hair shedding · Facial volume loss or loose skin · Gallbladder pain / gallstones · Stomach pain or cramping |
| Routes | Subcutaneous injection · Oral / sublingual / troche |
| Dose bands | under 0.25 mg/week · 0.25 to under 0.5 mg/week · 0.5 to under 1 mg/week · 1 to under 2 mg/week · 2 mg/week or more |
| Frequency | About once a week · More than once a day · Less than weekly · Once a day · In cycles (weeks on, weeks off) |

#### Cagrilintide  `cagrilintide`

*Also known as:* cagri, Cagri, cag, cagrilintide, AM833, NNC0174-0833, CagriSema (fixed combo with semaglutide), reta/cagri blend

*Human evidence:* large-rcts

| | |
|---|---|
| Goals | Adding to a GLP-1 for extra effect · Appetite control / quieting food noise · Breaking a weight-loss plateau · Losing fat while keeping or building muscle · Fat loss / weight loss |
| Adverse effects (in addition to universal) | Constipation · Getting full very fast / eating too little · Acid reflux, bloating, burping or sulfur burps · Diarrhea or loose stools |
| Routes | Subcutaneous injection |
| Dose bands | under 0.5 mg/week · 0.5 to under 1 mg/week · 1 to under 2 mg/week · 2 mg/week or more |
| Frequency | About once a week · More than once a day · Less than weekly · In cycles (weeks on, weeks off) |

#### Mazdutide  `mazdutide`

*Also known as:* mazdu, mazdutide, IBI362, LY3305677, Xinermei, 信尔美, GLP-1/glucagon dual

*Human evidence:* large-rcts

| | |
|---|---|
| Goals | Fat loss / weight loss · Reducing liver fat · Breaking a weight-loss plateau |
| Adverse effects (in addition to universal) | Diarrhea or loose stools · Constipation · Racing heart, palpitations or higher resting heart rate · Acid reflux, bloating, burping or sulfur burps |
| Routes | Subcutaneous injection |
| Dose bands | under 2 mg/week · 2 to under 4 mg/week · 4 to under 6 mg/week · 6 mg/week or more |
| Frequency | About once a week · More than once a day · In cycles (weeks on, weeks off) |

#### Survodutide  `survodutide`

*Also known as:* survo, Survo, survodutide, BI 456906, GLP-1/glucagon dual

*Human evidence:* large-rcts

| | |
|---|---|
| Goals | Fat loss / weight loss · Reducing liver fat · Breaking a weight-loss plateau · Adding to a GLP-1 for extra effect |
| Adverse effects (in addition to universal) | Diarrhea or loose stools · Constipation · Acid reflux, bloating, burping or sulfur burps · Racing heart, palpitations or higher resting heart rate · Low blood sugar episodes (shaky, sweaty, weak) |
| Routes | Subcutaneous injection |
| Dose bands | under 1.2 mg/week · 1.2 to under 2.4 mg/week · 2.4 to under 3.6 mg/week · 3.6 mg/week or more |
| Frequency | About once a week · More than once a day · In cycles (weeks on, weeks off) |

#### Liraglutide  `liraglutide`

*Also known as:* lira, liraglutide, Victoza, Saxenda, generic liraglutide

*Human evidence:* large-rcts

| | |
|---|---|
| Goals | Fat loss / weight loss · Blood sugar / insulin resistance / A1c · Alternative to weekly GLP-1 injections (oral / daily / cheaper) |
| Adverse effects (in addition to universal) | Diarrhea or loose stools · Constipation · Low blood sugar episodes (shaky, sweaty, weak) · Gallbladder pain / gallstones · Racing heart, palpitations or higher resting heart rate |
| Routes | Subcutaneous injection |
| Dose bands | under 1.2 mg/day · 1.2 to under 1.8 mg/day · 1.8 to under 3 mg/day · 3 mg/day or more |
| Frequency | Once a day · More than once a day · In cycles (weeks on, weeks off) |

### Growth hormone axis

#### CJC-1295 (no DAC) / ipamorelin blend  `cjc-1295-ipamorelin-blend`

*Also known as:* CJC/Ipa, CJC-1295 ipamorelin, Mod GRF 1-29 / ipamorelin, ipamorelin/CJC, GH stack, 5mg/5mg blend, 10mg blend

*Human evidence:* small-trials

| | |
|---|---|
| Goals | Deeper, more restorative sleep · Fat loss / weight loss · Losing fat while keeping or building muscle · Faster recovery from training · Healing a tendon, ligament, muscle or joint injury · Skin appearance / fine lines / anti-aging look · Raising IGF-1 / GH on bloodwork |
| Adverse effects (in addition to universal) | Acid reflux, bloating, burping or sulfur burps · Tingling or numb hands / fingers · Intense hunger or rebound cravings · Elevated fasting blood sugar or insulin resistance on labs |
| Routes | Subcutaneous injection |
| Dose bands | under 100 mcg of each per injection · 100-150 mcg of each per injection · 151-250 mcg of each per injection · 251-400 mcg of each per injection · over 400 mcg of each per injection |
| Frequency | Once a day · More than once a day · 5 days on / 2 days off · Every other day · In cycles (weeks on, weeks off) |

#### Ipamorelin  `ipamorelin`

*Also known as:* Ipa, ipamorelin acetate, NNC 26-0161

*Human evidence:* small-trials

| | |
|---|---|
| Goals | Deeper, more restorative sleep · Fat loss / weight loss · Losing fat while keeping or building muscle · Faster recovery from training · Healing a tendon, ligament, muscle or joint injury · Skin appearance / fine lines / anti-aging look · Raising IGF-1 / GH on bloodwork |
| Adverse effects (in addition to universal) | Acid reflux, bloating, burping or sulfur burps · Intense hunger or rebound cravings · Tingling or numb hands / fingers · Elevated fasting blood sugar or insulin resistance on labs |
| Routes | Subcutaneous injection |
| Dose bands | under 100 mcg per injection · 100-150 mcg per injection · 151-250 mcg per injection · 251-400 mcg per injection · over 400 mcg per injection |
| Frequency | Once a day · More than once a day · 5 days on / 2 days off · Every other day · In cycles (weeks on, weeks off) |

#### Tesamorelin  `tesamorelin`

*Also known as:* Tesa, Egrifta, TH9507, tesamorelin acetate, Egrifta SV, Egrifta WR

*Human evidence:* large-rcts

| | |
|---|---|
| Goals | Reducing belly / visceral fat specifically · Reducing liver fat · Losing fat while keeping or building muscle · Less brain fog / mental fatigue · Deeper, more restorative sleep · Faster recovery from training · Raising IGF-1 / GH on bloodwork |
| Adverse effects (in addition to universal) | Joint pain or stiffness · Muscle cramps or aches · Swollen ankles or feet · Tingling or numb hands / fingers · Elevated fasting blood sugar or insulin resistance on labs · Skin irritation, rash, hives or breakouts |
| Routes | Subcutaneous injection |
| Dose bands | under 1 mg per day · 1 mg per day (1-1.4 mg) · 1.5-2 mg per day · 2.1-3 mg per day · over 3 mg per day |
| Frequency | Once a day · 5 days on / 2 days off · Every other day · In cycles (weeks on, weeks off) |

#### MK-677 (ibutamoren)  `mk-677`

*Also known as:* MK-677, MK677, ibutamoren, ibutamoren mesylate, Nutrobal, L-163,191, LUM-201

*Human evidence:* large-rcts

| | |
|---|---|
| Goals | Increasing appetite (bulking) · Muscle gain · Deeper, more restorative sleep · Healing a tendon, ligament, muscle or joint injury · Skin appearance / fine lines / anti-aging look · Bone density · Raising IGF-1 / GH on bloodwork |
| Adverse effects (in addition to universal) | Intense hunger or rebound cravings · Acid reflux, bloating, burping or sulfur burps · Tingling or numb hands / fingers · Elevated fasting blood sugar or insulin resistance on labs · Joint pain or stiffness · Swollen ankles or feet · Unwanted weight gain · Muscle cramps or aches |
| Routes | Oral / sublingual / troche |
| Dose bands | under 10 mg per day · 10-12.5 mg per day · 13-25 mg per day · 26-50 mg per day · over 50 mg per day |
| Frequency | Once a day · More than once a day · 5 days on / 2 days off · Every other day · In cycles (weeks on, weeks off) |

#### Somatropin (HGH)  `somatropin`

*Also known as:* HGH, GH, growth hormone, somatropin, rhGH, generic HGH, blue tops, Genotropin

*Human evidence:* large-rcts

| | |
|---|---|
| Goals | Fat loss / weight loss · Muscle gain · Healing a tendon, ligament, muscle or joint injury · Skin appearance / fine lines / anti-aging look · Deeper, more restorative sleep · Faster recovery from training · Raising IGF-1 / GH on bloodwork |
| Adverse effects (in addition to universal) | Acid reflux, bloating, burping or sulfur burps · Joint pain or stiffness · Tingling or numb hands / fingers · Elevated fasting blood sugar or insulin resistance on labs · Swollen ankles or feet · New skin tags or moles |
| Routes | Subcutaneous injection · Intramuscular injection |
| Dose bands | under 2 IU per day · 2-3 IU per day · 3.1-4 IU per day · 4.1-6 IU per day · 6.1-10 IU per day · over 10 IU per day |
| Frequency | Once a day · More than once a day · 5 days on / 2 days off · Every other day · In cycles (weeks on, weeks off) |

#### CJC-1295 without DAC (Mod GRF 1-29)  `cjc-1295-without-dac`

*Also known as:* CJC no DAC, CJC-1295 no DAC, Mod GRF 1-29, Modified GRF (1-29), modified GRF, tetrasubstituted GRF 1-29, CJC 1295 NO-DAC

*Human evidence:* small-trials

| | |
|---|---|
| Goals | Raising IGF-1 / GH on bloodwork · Fat loss / weight loss · Losing fat while keeping or building muscle · Deeper, more restorative sleep · Faster recovery from training · Healing a tendon, ligament, muscle or joint injury |
| Adverse effects (in addition to universal) | Racing heart, palpitations or higher resting heart rate · Acid reflux, bloating, burping or sulfur burps · Tingling or numb hands / fingers · Elevated fasting blood sugar or insulin resistance on labs |
| Routes | Subcutaneous injection |
| Dose bands | under 100 mcg per injection · 100-150 mcg per injection · 151-250 mcg per injection · 251-400 mcg per injection · over 400 mcg per injection |
| Frequency | Once a day · More than once a day · 5 days on / 2 days off · Every other day · In cycles (weeks on, weeks off) |

#### Sermorelin  `sermorelin`

*Also known as:* sermorelin acetate, Geref, GRF 1-29, GHRH 1-29, serm

*Human evidence:* small-trials

| | |
|---|---|
| Goals | Deeper, more restorative sleep · More daily energy, less fatigue · Fat loss / weight loss · Losing fat while keeping or building muscle · Faster recovery from training · Skin appearance / fine lines / anti-aging look · Raising IGF-1 / GH on bloodwork |
| Adverse effects (in addition to universal) | Drowsiness or feeling flat / too calm · Taste changes · Skin irritation, rash, hives or breakouts · Water retention, bloating or puffy face/hands · Trouble swallowing (rare) |
| Routes | Subcutaneous injection |
| Dose bands | under 200 mcg per injection · 200-300 mcg per injection · 301-500 mcg per injection · 501-1000 mcg per injection · over 1000 mcg per injection |
| Frequency | Once a day · More than once a day · 5 days on / 2 days off · Every other day · In cycles (weeks on, weeks off) |

#### CJC-1295 with DAC  `cjc-1295-with-dac`

*Also known as:* CJC DAC, CJC-1295 DAC, CJC-1295 w/ DAC, DAC:GRF, drug affinity complex CJC

*Human evidence:* small-trials

| | |
|---|---|
| Goals | Raising IGF-1 / GH on bloodwork · Muscle gain · Fat loss / weight loss · Healing a tendon, ligament, muscle or joint injury · Faster recovery from training · Deeper, more restorative sleep |
| Adverse effects (in addition to universal) | Acid reflux, bloating, burping or sulfur burps · Joint pain or stiffness · Tingling or numb hands / fingers · Elevated fasting blood sugar or insulin resistance on labs · Intense hunger or rebound cravings · Racing heart, palpitations or higher resting heart rate |
| Routes | Subcutaneous injection |
| Dose bands | under 1 mg per week · 1-1.9 mg per week · 2-2.9 mg per week · 3-4 mg per week · over 4 mg per week |
| Frequency | About once a week · More than once a day · Less than weekly · In cycles (weeks on, weeks off) |

#### GHRP-6  `ghrp-6`

*Also known as:* GHRP6, growth hormone releasing peptide-6, His-D-Trp-Ala-Trp-D-Phe-Lys, SKF-110679

*Human evidence:* small-trials

| | |
|---|---|
| Goals | Increasing appetite (bulking) · Muscle gain · Healing a tendon, ligament, muscle or joint injury · Faster recovery from training · Deeper, more restorative sleep · Gut issues (IBS, ulcers, leaky gut, inflammation) · Fat loss / weight loss |
| Adverse effects (in addition to universal) | Intense hunger or rebound cravings · Acid reflux, bloating, burping or sulfur burps · Tingling or numb hands / fingers · Low libido or nipple tenderness · Elevated fasting blood sugar or insulin resistance on labs |
| Routes | Subcutaneous injection |
| Dose bands | under 100 mcg per injection · 100-150 mcg per injection · 151-250 mcg per injection · 251-400 mcg per injection · over 400 mcg per injection |
| Frequency | Once a day · More than once a day · 5 days on / 2 days off · In cycles (weeks on, weeks off) |

#### GHRP-2 (pralmorelin)  `ghrp-2`

*Also known as:* GHRP2, pralmorelin, KP-102, GHRP Kaken 100, growth hormone releasing peptide-2

*Human evidence:* small-trials

| | |
|---|---|
| Goals | Muscle gain · Fat loss / weight loss · Faster recovery from training · Healing a tendon, ligament, muscle or joint injury · Deeper, more restorative sleep · Raising IGF-1 / GH on bloodwork |
| Adverse effects (in addition to universal) | Intense hunger or rebound cravings · Acid reflux, bloating, burping or sulfur burps · Tingling or numb hands / fingers · Low libido or nipple tenderness · Elevated fasting blood sugar or insulin resistance on labs |
| Routes | Subcutaneous injection |
| Dose bands | under 100 mcg per injection · 100-150 mcg per injection · 151-250 mcg per injection · 251-400 mcg per injection · over 400 mcg per injection |
| Frequency | Once a day · More than once a day · 5 days on / 2 days off · In cycles (weeks on, weeks off) |

#### Hexarelin  `hexarelin`

*Also known as:* examorelin, Hex, hexarelin acetate, EP 23905

*Human evidence:* small-trials

| | |
|---|---|
| Goals | Muscle gain · Healing a tendon, ligament, muscle or joint injury · Heart or kidney protection · Fat loss / weight loss · Faster recovery from training · Raising IGF-1 / GH on bloodwork |
| Adverse effects (in addition to universal) | Low libido or nipple tenderness · Acid reflux, bloating, burping or sulfur burps · Tingling or numb hands / fingers · Elevated fasting blood sugar or insulin resistance on labs |
| Routes | Subcutaneous injection |
| Dose bands | under 50 mcg per injection · 50-100 mcg per injection · 101-200 mcg per injection · 201-300 mcg per injection · over 300 mcg per injection |
| Frequency | Once a day · More than once a day · Every other day · In cycles (weeks on, weeks off) |

### Tissue repair / healing

#### GHK-Cu  `ghk-cu`

*Also known as:* GHK-Cu, copper peptide, GHK copper, Cu-GHK, glycyl-L-histidyl-L-lysine copper, GHK-Cu injectable, copper tripeptide-1

*Human evidence:* small-trials

| | |
|---|---|
| Goals | Skin appearance / fine lines / anti-aging look · Hair regrowth or thicker hair · Healing wounds, scars, acne marks or stretch marks · More even skin tone · Healing a tendon, ligament, muscle or joint injury · General longevity / anti-aging |
| Adverse effects (in addition to universal) | Blue-green staining or residue on skin · Skin irritation, rash, hives or breakouts · Hair shedding |
| Routes | Topical / transdermal · Subcutaneous injection |
| Dose bands | Topical only (no injection) · Under 1 mg per day injected · 1 to 2 mg per day injected · 2 to 4 mg per day injected · Over 4 mg per day injected |
| Frequency | Once a day · 5 days on / 2 days off · 2–3 times a week · About once a week · More than once a day · In cycles (weeks on, weeks off) |

#### BPC-157  `bpc-157`

*Also known as:* BPC157, BPC 157, Body Protection Compound-157, Bepecin, PL 14736, PL-10, BPC-157 acetate, BPC-157 arginate (see PDA)

*Human evidence:* small-trials

| | |
|---|---|
| Goals | Healing a tendon, ligament, muscle or joint injury · Joint or cartilage pain relief · Gut issues (IBS, ulcers, leaky gut, inflammation) · Recovery after surgery · Faster recovery from training · Recovery after concussion, head injury or stroke |
| Adverse effects (in addition to universal) | Racing heart, palpitations or higher resting heart rate · Acid reflux, bloating, burping or sulfur burps · Pain or inflammation got worse at the injury · Skin, gum or mole darkening |
| Routes | Subcutaneous injection · Oral / sublingual / troche · Nasal spray / drops · Intramuscular injection · Topical / transdermal |
| Dose bands | under 250 mcg per dose · 250 to under 500 mcg per dose · 500 mcg to 1 mg per dose · over 1 mg per dose |
| Frequency | Once a day · More than once a day · Every other day · In cycles (weeks on, weeks off) |

#### TB-500  `tb-500`

*Also known as:* TB500, TB 500, thymosin beta-4, thymosin β4, Tβ4, TB-4, TB4, Thymosin Beta 4 fragment

*Human evidence:* none

| | |
|---|---|
| Goals | An old or chronic injury that never fully healed · Healing a tendon, ligament, muscle or joint injury · Flexibility, mobility or stiffness · Joint or cartilage pain relief · Recovery after surgery · Faster recovery from training · Hair regrowth or thicker hair |
| Adverse effects (in addition to universal) | Flu-like or achy feeling for a day or two · Muscle cramps or aches · Skin, gum or mole darkening |
| Routes | Subcutaneous injection · Intramuscular injection · Oral / sublingual / troche · Nasal spray / drops |
| Dose bands | under 2 mg per dose · 2 to under 5 mg per dose · 5 to 10 mg per dose · over 10 mg per dose |
| Frequency | More than once a day · About once a week · Once a day · Every other day · In cycles (weeks on, weeks off) |

#### BPC-157 + TB-500 blend (Wolverine stack)  `bpc-157-tb-500-blend`

*Also known as:* Wolverine stack, Wolverine blend, Wolverine protocol, BPC/TB, BPC-157/TB-500 blend, BPC + TB, TB-500/BPC-157 10mg blend, healing stack

*Human evidence:* none

| | |
|---|---|
| Goals | Healing a tendon, ligament, muscle or joint injury · An old or chronic injury that never fully healed · Recovery after surgery · Joint or cartilage pain relief · Faster recovery from training · Gut issues (IBS, ulcers, leaky gut, inflammation) |
| Adverse effects (in addition to universal) | Flu-like or achy feeling for a day or two · Skin, gum or mole darkening |
| Routes | Subcutaneous injection · Intramuscular injection · Oral / sublingual / troche |
| Dose bands | under 500 mcg (combined) per dose · 500 mcg to under 1 mg per dose · 1 to 2 mg per dose · over 2 mg per dose |
| Frequency | Once a day · Every other day · More than once a day · In cycles (weeks on, weeks off) |

#### KPV  `kpv`

*Also known as:* KPV peptide, Lys-Pro-Val, alpha-MSH fragment (11-13), α-MSH 11-13, KPV acetate, KPV caps, oral KPV, KPV nasal spray

*Human evidence:* none

| | |
|---|---|
| Goals | Gut issues (IBS, ulcers, leaky gut, inflammation) · Skin condition (eczema, psoriasis, rosacea, acne) · Allergies, histamine or mast-cell issues · Autoimmune flares or body-wide inflammation · Sinus or respiratory issues · Healing wounds, scars, acne marks or stretch marks · Faster recovery from training |
| Adverse effects (in addition to universal) | Acid reflux, bloating, burping or sulfur burps · Skin irritation, rash, hives or breakouts · Flare-up of the condition being treated |
| Routes | Oral / sublingual / troche · Subcutaneous injection · Nasal spray / drops · Topical / transdermal |
| Dose bands | under 250 mcg per dose · 250 to under 500 mcg per dose · 500 mcg to 1 mg per dose · over 1 mg per dose |
| Frequency | Once a day · More than once a day · As needed / on demand · In cycles (weeks on, weeks off) |

#### LL-37  `ll-37`

*Also known as:* LL37, LL 37, cathelicidin, cathelicidin LL-37, hCAP18 fragment, CAP-18, ropocamptide (pharma name for topical LL-37), LL-37 acetate

*Human evidence:* small-trials

| | |
|---|---|
| Goals | Chronic or stealth infection (Lyme, mold, biofilm) · Immune support / fewer infections · Gut infection or dysbiosis (SIBO, candida) · Healing wounds, scars, acne marks or stretch marks · Skin condition (eczema, psoriasis, rosacea, acne) · Sinus or respiratory issues · Long COVID or chronic fatigue symptoms |
| Adverse effects (in addition to universal) | Flare-up of the condition being treated · Diarrhea or loose stools |
| Routes | Subcutaneous injection · Intramuscular injection · Nasal spray / drops · Topical / transdermal · Oral / sublingual / troche |
| Dose bands | under 50 mcg per dose · 50 to under 100 mcg per dose · 100 to 250 mcg per dose · over 250 mcg per dose |
| Frequency | More than once a day · Once a day · Every other day · As needed / on demand · In cycles (weeks on, weeks off) |

#### ARA-290 (cibinetide)  `ara-290`

*Also known as:* ARA290, ARA 290, cibinetide, Cibinetide (ARA-290), helix-B surface peptide, HBSP, pyroglutamate helix B surface peptide, innate repair receptor agonist

*Human evidence:* small-trials

| | |
|---|---|
| Goals | Nerve pain or neuropathy · Long COVID or chronic fatigue symptoms · Autoimmune flares or body-wide inflammation · Healing a tendon, ligament, muscle or joint injury |
| Adverse effects (in addition to universal) | Pain or inflammation got worse at the injury |
| Routes | Subcutaneous injection |
| Dose bands | under 2 mg per dose · 2 to under 4 mg per dose · 4 to 6 mg per dose · over 6 mg per dose |
| Frequency | Once a day · In cycles (weeks on, weeks off) |

### Nootropic / mood / sleep

#### Oxytocin (intranasal)  `oxytocin`

*Also known as:* oxytocin, oxytocin nasal spray, OT, OXT, Syntocinon, oxytocin troche

*Human evidence:* small-trials

| | |
|---|---|
| Goals | Feeling calmer or more at ease socially · Closer bonding or intimacy with a partner · More intense arousal or orgasm · Better mood / lifting depression · Less anxiety or stress · Deeper, more restorative sleep |
| Adverse effects (in addition to universal) | Feeling weepy or emotionally raw · Cramping (women) |
| Routes | Nasal spray / drops · Oral / sublingual / troche · Subcutaneous injection |
| Dose bands | Under 10 IU per dose · 10 to under 20 IU per dose · 20 to under 30 IU per dose · 30 to 50 IU per dose · Over 50 IU per dose |
| Frequency | As needed / on demand · Once a day · More than once a day · 2–3 times a week · In cycles (weeks on, weeks off) |

#### DSIP (delta sleep-inducing peptide)  `dsip`

*Also known as:* DSIP, delta sleep-inducing peptide, emideltide, sleep peptide

*Human evidence:* small-trials

| | |
|---|---|
| Goals | Falling asleep faster · Deeper, more restorative sleep · More daily energy, less fatigue · Less anxiety or stress |
| Adverse effects (in addition to universal) |  |
| Routes | Subcutaneous injection · Nasal spray / drops |
| Dose bands | Under 100 mcg per dose · 100 to under 200 mcg per dose · 200 to under 400 mcg per dose · 400 mcg to 1 mg per dose · Over 1 mg per dose |
| Frequency | Once a day · 2–3 times a week · As needed / on demand · In cycles (weeks on, weeks off) |

#### Semax  `semax`

*Also known as:* Semax, NA-Semax, N-Acetyl Semax, NA-Semax Amidate, N-Acetyl Semax Amidate, Semax 0.1% / 1% nasal drops, ACTH(4-10) analog, Met-Glu-His-Phe-Pro-Gly-Pro

*Human evidence:* small-trials

| | |
|---|---|
| Goals | Sharper focus and concentration · Better memory and learning · More motivation and drive · Less brain fog / mental fatigue · Better mood / lifting depression · Recovery after concussion, head injury or stroke · Long-term brain health |
| Adverse effects (in addition to universal) | Hair shedding |
| Routes | Nasal spray / drops · Subcutaneous injection |
| Dose bands | under 200 mcg/day · 200-400 mcg/day · 400-800 mcg/day · 800-1,500 mcg/day · over 1,500 mcg/day |
| Frequency | Once a day · More than once a day · As needed / on demand · In cycles (weeks on, weeks off) |

#### Selank  `selank`

*Also known as:* Selank, TP-7, NA-Selank, N-Acetyl Selank, NA-Selank Amidate, Selank 0.15% nasal drops, tuftsin analog, Thr-Lys-Pro-Arg-Pro-Gly-Pro

*Human evidence:* small-trials

| | |
|---|---|
| Goals | Less anxiety or stress · Sharper focus and concentration · Better mood / lifting depression · Deeper, more restorative sleep · Easing withdrawal or tapering off a substance · Better memory and learning · Immune support / fewer infections |
| Adverse effects (in addition to universal) | Drowsiness or feeling flat / too calm · Brain fog or mental fatigue |
| Routes | Nasal spray / drops · Subcutaneous injection |
| Dose bands | under 250 mcg/day · 250-500 mcg/day · 500-1,000 mcg/day · 1,000-2,000 mcg/day · over 2,000 mcg/day |
| Frequency | Once a day · More than once a day · As needed / on demand · In cycles (weeks on, weeks off) |

#### Cerebrolysin  `cerebrolysin`

*Also known as:* Cerebrolysin, Cerebro, porcine brain peptide hydrolysate, EVER Pharma Cerebrolysin ampoules, Cerebrolysin 5ml / 10ml

*Human evidence:* large-rcts

| | |
|---|---|
| Goals | Recovery after concussion, head injury or stroke · Slowing memory loss or cognitive decline · Sharper focus and concentration · Better mood / lifting depression · Less brain fog / mental fatigue · Long-term brain health |
| Adverse effects (in addition to universal) | Skin irritation, rash, hives or breakouts |
| Routes | Intramuscular injection · Subcutaneous injection · Intravenous (clinic) |
| Dose bands | 1 ml/day or less · 1-2 ml/day · 2-5 ml/day · 5-10 ml/day · over 10 ml/day |
| Frequency | Once a day · 5 days on / 2 days off · Every other day · More than once a day · In cycles (weeks on, weeks off) |

#### Dihexa  `dihexa`

*Also known as:* Dihexa, PNB-0408, N-hexanoic-Tyr-Ile-(6)-aminohexanoic amide, angiotensin IV analog, HGF/c-Met potentiator

*Human evidence:* none

| | |
|---|---|
| Goals | Better memory and learning · Sharper focus and concentration · Recovery after concussion, head injury or stroke · Slowing memory loss or cognitive decline · Better mood / lifting depression · Verbal fluency or creativity |
| Adverse effects (in addition to universal) | Skin irritation, rash, hives or breakouts · Blood pressure changes |
| Routes | Oral / sublingual / troche · Topical / transdermal · Subcutaneous injection · Nasal spray / drops |
| Dose bands | under 2 mg/day · 2-5 mg/day · 5-10 mg/day · 10-20 mg/day · over 20 mg/day |
| Frequency | Once a day · Every other day · More than once a day · In cycles (weeks on, weeks off) |

#### P21 (P021)  `p21`

*Also known as:* P21, P021, Ac-DGGLAG-NH2 (adamantylated), CNTF mimetic peptide, CNTF fragment peptide

*Human evidence:* none

| | |
|---|---|
| Goals | Better memory and learning · Long-term brain health · Better mood / lifting depression · Sharper focus and concentration · Recovery after concussion, head injury or stroke · Less anxiety or stress |
| Adverse effects (in addition to universal) |  |
| Routes | Nasal spray / drops · Subcutaneous injection |
| Dose bands | under 250 mcg/day · 250-500 mcg/day · 500-1,000 mcg/day · 1-2 mg/day · over 2 mg/day |
| Frequency | Once a day · More than once a day · Every other day · In cycles (weeks on, weeks off) |

#### Pinealon  `pinealon`

*Also known as:* Pinealon, EDR peptide, Glu-Asp-Arg, Khavinson brain bioregulator, Pinealon capsules (bioregulator)

*Human evidence:* case-reports

| | |
|---|---|
| Goals | Deeper, more restorative sleep · Better memory and learning · Better mood / lifting depression · Long-term brain health · Less anxiety or stress · Recovery after concussion, head injury or stroke |
| Adverse effects (in addition to universal) |  |
| Routes | Subcutaneous injection · Nasal spray / drops · Oral / sublingual / troche |
| Dose bands | under 1 mg/day · 1-2 mg/day · 2-5 mg/day · 5-10 mg/day · over 10 mg/day |
| Frequency | Once a day · In cycles (weeks on, weeks off) |

### Metabolic / longevity

#### AOD-9604  `aod-9604`

*Also known as:* AOD9604, AOD, HGH fragment 176-191 (sibling), Frag 176-191, anti-obesity drug 9604, Tyr-hGH177-191

*Human evidence:* small-trials

| | |
|---|---|
| Goals | Fat loss / weight loss · Joint or cartilage pain relief · Faster recovery from training · Blood sugar / insulin resistance / A1c |
| Adverse effects (in addition to universal) | Acid reflux, bloating, burping or sulfur burps |
| Routes | Subcutaneous injection · Oral / sublingual / troche · Intramuscular injection |
| Dose bands | under 250 mcg per day · 250-300 mcg per day · 301-500 mcg per day · 501-1000 mcg per day · over 1000 mcg per day |
| Frequency | Once a day · 5 days on / 2 days off · In cycles (weeks on, weeks off) |

#### NAD+ (injectable)  `nad`

*Also known as:* NAD+, NAD, nicotinamide adenine dinucleotide, NAD+ injections, NAD+ subq, NAD shots, beta-NAD, NAD+ IV

*Human evidence:* small-trials

| | |
|---|---|
| Goals | More daily energy, less fatigue · Less brain fog / mental fatigue · General longevity / anti-aging · Cutting alcohol, nicotine or other cravings · Deeper, more restorative sleep · Faster recovery from training · Long COVID or chronic fatigue symptoms · Better mood / lifting depression |
| Adverse effects (in addition to universal) | Chest tightness or pressure · Muscle cramps or aches · Diarrhea or loose stools |
| Routes | Subcutaneous injection · Intramuscular injection · Intravenous (clinic) · Nasal spray / drops · Oral / sublingual / troche |
| Dose bands | under 50 mg per injection · 50 to under 100 mg per injection · 100 to under 200 mg per injection · 200 to under 500 mg per injection · 500 mg or more per injection |
| Frequency | Once a day · Every other day · More than once a day · About once a week · In cycles (weeks on, weeks off) |

#### MOTS-c  `mots-c`

*Also known as:* MOTS-C, MOTSc, Mots-c, mitochondrial ORF of the 12S rRNA type-c, mitochondrial peptide MOTS-c

*Human evidence:* small-trials

| | |
|---|---|
| Goals | Losing fat while keeping or building muscle · Blood sugar / insulin resistance / A1c · More endurance / exercise capacity · More daily energy, less fatigue · Faster recovery from training · General longevity / anti-aging · Bone density |
| Adverse effects (in addition to universal) | Low blood sugar episodes (shaky, sweaty, weak) |
| Routes | Subcutaneous injection · Intramuscular injection |
| Dose bands | under 2.5 mg per injection · 2.5 to under 5 mg per injection · 5 to under 10 mg per injection · 10 to under 20 mg per injection · 20 mg or more per injection |
| Frequency | Once a day · Every other day · More than once a day · About once a week · In cycles (weeks on, weeks off) |

#### Epitalon  `epitalon`

*Also known as:* Epithalon, Epitalone, Epithalone, Epithalamin (related pineal extract), AEDG peptide, Ala-Glu-Asp-Gly, Khavinson peptide

*Human evidence:* small-trials

| | |
|---|---|
| Goals | General longevity / anti-aging · Deeper, more restorative sleep · More daily energy, less fatigue · Immune support / fewer infections · Skin appearance / fine lines / anti-aging look · Better mood / lifting depression · Periodic 'reset' course |
| Adverse effects (in addition to universal) | Drowsiness or feeling flat / too calm |
| Routes | Subcutaneous injection · Intramuscular injection · Nasal spray / drops · Oral / sublingual / troche |
| Dose bands | under 2.5 mg per day · 2.5 to under 5 mg per day · 5 to under 10 mg per day · 10 to under 20 mg per day · 20 mg or more per day |
| Frequency | Once a day · Every other day · More than once a day · In cycles (weeks on, weeks off) |

#### 5-amino-1MQ  `5-amino-1mq`

*Also known as:* 5-Amino-1MQ, 5-amino-1-methylquinolinium, 5A1MQ, 5-AMQ, 5 amino 1MQ, NNMT inhibitor

*Human evidence:* none

| | |
|---|---|
| Goals | Fat loss / weight loss · Losing fat while keeping or building muscle · More daily energy, less fatigue · Appetite control / quieting food noise · Blood sugar / insulin resistance / A1c · General longevity / anti-aging |
| Adverse effects (in addition to universal) | Diarrhea or loose stools · Low blood sugar episodes (shaky, sweaty, weak) |
| Routes | Oral / sublingual / troche · Subcutaneous injection |
| Dose bands | under 50 mg per day · 50 to under 100 mg per day · 100 to under 150 mg per day · 150 to under 250 mg per day · 250 mg or more per day |
| Frequency | Once a day · More than once a day · 5 days on / 2 days off · In cycles (weeks on, weeks off) |

#### Glutathione (injectable)  `glutathione`

*Also known as:* glutathione, GSH, L-glutathione, reduced glutathione, glutathione shots, TAD 600, Tathion

*Human evidence:* small-trials

| | |
|---|---|
| Goals | Skin brightening or lightening · Liver support / 'detox' · More daily energy, less fatigue · Immune support / fewer infections · Hangover or post-drinking recovery · General longevity / anti-aging · Faster recovery from training |
| Adverse effects (in addition to universal) | Stomach pain or cramping · Skin irritation, rash, hives or breakouts · Chest tightness or pressure · Unwanted skin lightening |
| Routes | Subcutaneous injection · Intramuscular injection · Intravenous (clinic) · Nasal spray / drops |
| Dose bands | under 200 mg per injection · 200 to under 400 mg per injection · 400 to under 800 mg per injection · 800 to under 1500 mg per injection · 1500 mg or more per injection |
| Frequency | Once a day · Every other day · More than once a day · About once a week · In cycles (weeks on, weeks off) |

#### Thymosin alpha-1  `thymosin-alpha-1`

*Also known as:* Thymosin alpha 1, Ta1, Tα1, TA-1, thymalfasin, Zadaxin, thymosin a1, T-alpha-1

*Human evidence:* large-rcts

| | |
|---|---|
| Goals | Long COVID or chronic fatigue symptoms · Immune support / fewer infections · Chronic or stealth infection (Lyme, mold, biofilm) · Autoimmune flares or body-wide inflammation · Adjunct during cancer treatment · Hepatitis B or C · More daily energy, less fatigue |
| Adverse effects (in addition to universal) | Skin irritation, rash, hives or breakouts · Flu-like or achy feeling for a day or two · Muscle cramps or aches |
| Routes | Subcutaneous injection |
| Dose bands | under 1 mg per injection · 1 to under 1.5 mg per injection · 1.5 to under 2 mg per injection · 2 to under 4 mg per injection · 4 mg or more per injection |
| Frequency | More than once a day · Once a day · About once a week · In cycles (weeks on, weeks off) |

#### Tesofensine  `tesofensine`

*Also known as:* Teso, NS2330, NS-2330, Tesomet (combination with metoprolol), tesofensine capsules

*Human evidence:* large-rcts

| | |
|---|---|
| Goals | Fat loss / weight loss · Appetite control / quieting food noise · More daily energy, less fatigue · Alternative to weekly GLP-1 injections (oral / daily / cheaper) · Maintaining weight after a prior loss (low-dose / microdose) |
| Adverse effects (in addition to universal) | Dry mouth · Racing heart, palpitations or higher resting heart rate · Blood pressure changes · Constipation · Sweating |
| Routes | Oral / sublingual / troche |
| Dose bands | under 0.25 mg per day · 0.25 to under 0.5 mg per day · 0.5 to under 1 mg per day · 1 mg or more per day |
| Frequency | Once a day · Every other day · In cycles (weeks on, weeks off) |

#### SS-31 (elamipretide)  `ss-31`

*Also known as:* SS-31, SS31, elamipretide, Bendavia, MTP-131, Forzinity, Szeto-Schiller 31

*Human evidence:* large-rcts

| | |
|---|---|
| Goals | More daily energy, less fatigue · General longevity / anti-aging · Heart or kidney protection · More endurance / exercise capacity · Long-term brain health · Eye health · Long COVID or chronic fatigue symptoms |
| Adverse effects (in addition to universal) | Acid reflux, bloating, burping or sulfur burps · Flu-like or achy feeling for a day or two · Muscle cramps or aches |
| Routes | Subcutaneous injection · Intravenous (clinic) |
| Dose bands | under 1 mg per day · 1 to under 2.5 mg per day · 2.5 to under 5 mg per day · 5 to under 10 mg per day · 10 mg or more per day |
| Frequency | Once a day · 5 days on / 2 days off · Every other day · In cycles (weeks on, weeks off) |

#### Humanin  `humanin`

*Also known as:* HN, humanin peptide, HNG, S14G-humanin, humanin analog, MT-hn

*Human evidence:* none

| | |
|---|---|
| Goals | General longevity / anti-aging · Blood sugar / insulin resistance / A1c · Long-term brain health · Heart or kidney protection · More daily energy, less fatigue |
| Adverse effects (in addition to universal) |  |
| Routes | Subcutaneous injection |
| Dose bands | under 0.5 mg per injection · 0.5 to under 1 mg per injection · 1 to under 2.5 mg per injection · 2.5 to under 5 mg per injection · 5 mg or more per injection |
| Frequency | Once a day · Every other day · More than once a day · In cycles (weeks on, weeks off) |

#### SLU-PP-332  `slu-pp-332`

*Also known as:* SLU PP 332, SLU-PP332, ERR agonist, exercise mimetic SLU

*Human evidence:* none

| | |
|---|---|
| Goals | More endurance / exercise capacity · Fat loss / weight loss · More daily energy, less fatigue |
| Adverse effects (in addition to universal) | Racing heart, palpitations or higher resting heart rate · Sweating |
| Routes | Oral / sublingual / troche · Subcutaneous injection |
| Dose bands | under 0.5 mg per day · 0.5 to under 2 mg per day · 2 to under 10 mg per day · 10 to under 30 mg per day · 30 mg or more per day |
| Frequency | Once a day · As needed / on demand · 5 days on / 2 days off · In cycles (weeks on, weeks off) |

#### FOXO4-DRI  `foxo4-dri`

*Also known as:* FOXO4 D-retro-inverso, FOXO4-DRI peptide, Proxofim, FOXO4 DRI, senolytic peptide

*Human evidence:* none

| | |
|---|---|
| Goals | General longevity / anti-aging · Joint or cartilage pain relief · Skin appearance / fine lines / anti-aging look · More daily energy, less fatigue · Heart or kidney protection |
| Adverse effects (in addition to universal) | Flu-like or achy feeling for a day or two · Muscle cramps or aches |
| Routes | Subcutaneous injection |
| Dose bands | under 1 mg per injection · 1 to under 2.5 mg per injection · 2.5 to under 5 mg per injection · 5 to under 10 mg per injection · 10 mg or more per injection |
| Frequency | Every other day · Once a day · In cycles (weeks on, weeks off) |

### Sexual function / hormonal

#### PT-141 (bremelanotide)  `pt-141`

*Also known as:* PT-141, PT141, bremelanotide, Vyleesi, BMT, PT-141 nasal

*Human evidence:* large-rcts

| | |
|---|---|
| Goals | Stronger sexual desire / libido · Firmer or more reliable erections · Add-on when ED medication is not enough · More intense arousal or orgasm |
| Adverse effects (in addition to universal) | Racing heart, palpitations or higher resting heart rate · New or darkening moles / freckles · Unwanted or prolonged erections |
| Routes | Subcutaneous injection · Nasal spray / drops |
| Dose bands | Under 0.5 mg per dose · 0.5 to under 1 mg per dose · 1 to under 1.5 mg per dose · 1.5 to 2 mg per dose · Over 2 mg per dose |
| Frequency | As needed / on demand · 2–3 times a week · Once a day · In cycles (weeks on, weeks off) |

#### Melanotan II  `melanotan-ii`

*Also known as:* Melanotan II, Melanotan 2, MT-2, MT2, MTII, melanotan, tanning peptide, Barbie drug

*Human evidence:* small-trials

| | |
|---|---|
| Goals | Darker tan with less sun exposure · Tanning without burning / sun sensitivity · Stronger sexual desire / libido · Appetite control / quieting food noise · More even skin tone |
| Adverse effects (in addition to universal) | Unwanted or prolonged erections · New or darkening moles / freckles · Uneven skin darkening |
| Routes | Subcutaneous injection · Nasal spray / drops |
| Dose bands | Under 100 mcg per dose · 100 to under 250 mcg per dose · 250 to under 500 mcg per dose · 500 mcg to 1 mg per dose · Over 1 mg per dose |
| Frequency | Once a day · Every other day · 2–3 times a week · About once a week · In cycles (weeks on, weeks off) |

#### Kisspeptin-10  `kisspeptin-10`

*Also known as:* Kisspeptin-10, kisspeptin, KP-10, KISS1, metastin fragment, kiss peptide

*Human evidence:* small-trials

| | |
|---|---|
| Goals | Higher natural testosterone · Stronger sexual desire / libido · Restoring hormone function after a cycle or TRT · Fertility · Better mood / lifting depression |
| Adverse effects (in addition to universal) | Acne or oily skin |
| Routes | Subcutaneous injection · Nasal spray / drops |
| Dose bands | Under 50 mcg per dose · 50 to under 100 mcg per dose · 100 to under 250 mcg per dose · 250 to 500 mcg per dose · Over 500 mcg per dose |
| Frequency | As needed / on demand · Once a day · Every other day · 2–3 times a week · In cycles (weeks on, weeks off) |

#### Melanotan I (afamelanotide)  `melanotan-i`

*Also known as:* Melanotan I, Melanotan 1, MT-1, MT1, MTI, afamelanotide, Scenesse, NDP-alpha-MSH

*Human evidence:* small-trials

| | |
|---|---|
| Goals | Darker tan with less sun exposure · Tanning without burning / sun sensitivity · More even skin tone |
| Adverse effects (in addition to universal) | New or darkening moles / freckles · Uneven skin darkening |
| Routes | Subcutaneous injection |
| Dose bands | Under 0.5 mg per dose · 0.5 to under 1 mg per dose · 1 to 2 mg per dose · Over 2 mg per dose |
| Frequency | Once a day · Every other day · 2–3 times a week · About once a week · In cycles (weeks on, weeks off) |

#### Gonadorelin  `gonadorelin`

*Also known as:* gonadorelin, GnRH, gonadorelin acetate, Factrel, LHRH

*Human evidence:* small-trials

| | |
|---|---|
| Goals | Keeping testicular function or fertility while on TRT · Restoring hormone function after a cycle or TRT · Higher natural testosterone |
| Adverse effects (in addition to universal) | Acne or oily skin · Acid reflux, bloating, burping or sulfur burps |
| Routes | Subcutaneous injection · Nasal spray / drops |
| Dose bands | Under 100 mcg per dose · 100 to under 200 mcg per dose · 200 to 500 mcg per dose · Over 500 mcg per dose |
| Frequency | Once a day · Every other day · 2–3 times a week · About once a week |

## Uniqueness analysis

`tools/uniqueness.py synthetic spec/schema.config.json` generates rows from this schema under
stated skew assumptions and reports how many are unique on several quasi-identifier sets. This
is published so the identifiability of the store is a stated number, not a claim.

**Assumptions:** compound prevalence Zipf(s=1.0) over 30 compounds; dose bands middle-heavy; one
goal per row, Zipf(0.8) within the compound's list; age and sex skewed to the community's known
demographics; source channel dominated by research-chemical vendors. These are assumptions
made before any data existed. The same tool runs in `real` mode on the private store before every release, and the
summary numbers (never rows) are published with the release.

| Quasi-identifier set | Fields | n=500 | n=5,000 | n=50,000 |
|---|---|---|---|---|
| Detailed post | 7 | 97.2% unique | 89.3% unique | 58.0% unique |
| Typical post | 5 | 80.2% unique | 40.1% unique | 9.3% unique |
| Typical post, no dose | 4 | 53.8% unique | 16.2% unique | 1.7% unique |
| Compound + age + sex | 3 | 24.8% unique | 2.9% unique | 0.1% unique |
| Entire row | 15 | 100.0% unique | 100.0% unique | 100.0% unique |

**What this means.** On the entire row, the store is near-unique at every size — that is the
nature of a schema rich enough to be useful, and no amount of coarsening changes it without
destroying the data. On what a typical detailed public post reveals — compound, age band, sex,
goal, and dose band — roughly a third of rows are unique at n=5,000. Someone who obtained the
raw store *and* had read a contributor's detailed post could shortlist that contributor's row.

**Why this does not make the row personal data, and what does the work instead.** The
de-identification argument does not rest on row-level k-anonymity; it rests on four things.
There is no direct or persistent identifier, no IP, no location. The coarsening removes the
precision an adversary needs — a public post gives a dose, not a dose band; a start date, not a
duration bucket. The store is never published, so linkage requires both a breach or subpoena
*and* auxiliary information about a specific target. And the statutory three-part test
(reasonable measures, a public commitment not to re-identify, downstream contractual obligations)
does not require k-anonymity. Under the EU singling-out test the argument is harder, which is
why the site does not target the EEA.

**What the marginal analysis says.** With `quarter_started` removed and goal made single-select,
no one field dominates: at n=5,000, dropping any of goal, source channel, duration, age band or
dose band reduces uniqueness by roughly 20 points, and dropping compound reduces it by almost
nothing. Further coarsening of any single field would not change the picture. The fields kept
are the ones the dataset exists to collect.

## Change control

The taxonomy is versioned. Additions are batched and published on a schedule, never in response
to a single submission. A removed option is retained in the schema as deprecated so historical
rows remain interpretable. Every change increments the version and appears in the changelog.
