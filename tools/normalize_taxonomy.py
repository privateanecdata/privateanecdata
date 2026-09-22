#!/usr/bin/env python3
"""
Normalize the researched per-compound vocabularies into a frozen taxonomy.

Input:  $PA_RESEARCH or ~/privateanecdata-research/taxonomy.research.json  (raw research output; kept OUTSIDE the repository)
Output: spec/taxonomy.v1.json         (frozen, normalized)
        spec/schema.config.json       (uniqueness.py config derived from it)

Normalization is a hand-maintained mapping from researched phrasing -> canonical id. Anything
unmapped is printed so the mapping can be extended. Nothing is silently dropped.

Universal adverse effects (asked for every compound) are separated from compound-specific ones
so the same effect is never listed twice on a form.
"""
import json
import os
import re
import sys
from collections import Counter, OrderedDict

# ------------------------------------------------------------------ goal vocabulary
# id -> display label. Order here is the order goals appear in the form.
GOALS = OrderedDict([
    # fat / weight
    ("fat-loss",            "Fat loss / weight loss"),
    ("visceral-fat",        "Reducing belly / visceral fat specifically"),
    ("recomp",              "Losing fat while keeping or building muscle"),
    ("plateau",             "Breaking a weight-loss plateau"),
    ("weight-maintenance",  "Maintaining weight after a prior loss (low-dose / microdose)"),
    ("appetite-control",    "Appetite control / quieting food noise"),
    ("appetite-increase",   "Increasing appetite (bulking)"),
    ("glp1-stack",          "Adding to a GLP-1 for extra effect"),
    # muscle / performance
    ("muscle-gain",         "Muscle gain"),
    ("training-recovery",   "Faster recovery from training"),
    ("endurance",           "More endurance / exercise capacity"),
    ("athletic-performance","Athletic performance"),
    # healing
    ("injury-healing",      "Healing a tendon, ligament, muscle or joint injury"),
    ("joint-pain",          "Joint or cartilage pain relief"),
    ("wound-scar",          "Healing wounds, scars, acne marks or stretch marks"),
    ("gut",                 "Gut issues (IBS, ulcers, leaky gut, inflammation)"),
    ("gut-infection",       "Gut infection or dysbiosis (SIBO, candida)"),
    ("chronic-injury",      "An old or chronic injury that never fully healed"),
    ("post-surgery",        "Recovery after surgery"),
    ("mobility",            "Flexibility, mobility or stiffness"),
    ("chronic-pain",        "Chronic pain"),
    ("nerve-pain",          "Nerve pain or neuropathy"),
    ("skin-condition",      "Skin condition (eczema, psoriasis, rosacea, acne)"),
    ("allergy-mcas",        "Allergies, histamine or mast-cell issues"),
    ("autoimmune",          "Autoimmune flares or body-wide inflammation"),
    ("sinus-respiratory",   "Sinus or respiratory issues"),
    ("infection",           "Chronic or stealth infection (Lyme, mold, biofilm)"),
    # metabolic
    ("blood-sugar",         "Blood sugar / insulin resistance / A1c"),
    ("pcos",                "PCOS-related weight or insulin issues"),
    ("liver-fat",           "Reducing liver fat"),
    ("cardio-kidney",       "Heart or kidney protection"),
    ("lipids",              "Cholesterol or other blood markers"),
    # cravings / substances
    ("cravings",            "Cutting alcohol, nicotine or other cravings"),
    ("withdrawal",          "Easing withdrawal or tapering off a substance"),
    # sleep
    ("deeper-sleep",        "Deeper, more restorative sleep"),
    ("fall-asleep",         "Falling asleep faster"),
    # cognitive
    ("focus",               "Sharper focus and concentration"),
    ("memory",              "Better memory and learning"),
    ("brain-fog",           "Less brain fog / mental fatigue"),
    ("cognitive-decline",   "Slowing memory loss or cognitive decline"),
    ("brain-injury",        "Recovery after concussion, head injury or stroke"),
    ("neuroprotection",     "Long-term brain health"),
    ("motivation",          "More motivation and drive"),
    ("verbal-creativity",   "Verbal fluency or creativity"),
    # mood
    ("mood",                "Better mood / lifting depression"),
    ("anxiety",             "Less anxiety or stress"),
    ("social-ease",         "Feeling calmer or more at ease socially"),
    # energy / longevity
    ("energy",              "More daily energy, less fatigue"),
    ("longevity",           "General longevity / anti-aging"),
    ("immune",              "Immune support / fewer infections"),
    ("long-covid",          "Long COVID or chronic fatigue symptoms"),
    ("bone-density",        "Bone density"),
    # appearance
    ("skin-aging",          "Skin appearance / fine lines / anti-aging look"),
    ("hair",                "Hair regrowth or thicker hair"),
    ("skin-tone",           "More even skin tone"),
    ("tan",                 "Darker tan with less sun exposure"),
    ("sun-tolerance",       "Tanning without burning / sun sensitivity"),
    # sexual / hormonal
    ("libido",              "Stronger sexual desire / libido"),
    ("erections",           "Firmer or more reliable erections"),
    ("orgasm",              "More intense arousal or orgasm"),
    ("ed-adjunct",          "Add-on when ED medication is not enough"),
    ("testosterone",        "Higher natural testosterone"),
    ("pct",                 "Restoring hormone function after a cycle or TRT"),
    ("fertility",           "Fertility"),
    ("bonding",             "Closer bonding or intimacy with a partner"),
    # labs / other
    ("igf1",                "Raising IGF-1 / GH on bloodwork"),
    ("annual-reset",        "Periodic 'reset' course"),
    ("trt-support",         "Keeping testicular function or fertility while on TRT"),
    ("glp1-alternative",    "Alternative to weekly GLP-1 injections (oral / daily / cheaper)"),
    ("skin-brightening",    "Skin brightening or lightening"),
    ("detox-liver",         "Liver support / 'detox'"),
    ("hangover",            "Hangover or post-drinking recovery"),
    ("cancer-adjunct",      "Adjunct during cancer treatment"),
    ("hepatitis",           "Hepatitis B or C"),
    ("eye-health",          "Eye health"),
])

# researched phrase (lowercased, stripped) -> goal id
GOAL_MAP = {
    # fat / weight
    "weight loss / fat loss": "fat-loss", "fat loss / weight loss": "fat-loss", "body fat loss": "fat-loss",
    "belly/body fat loss": "fat-loss", "fat loss": "fat-loss", "fat loss / body recomposition": "recomp",
    "overall weight loss without losing muscle": "recomp",
    "weight loss for people who cannot tolerate glp-1s (used alone)": "fat-loss",
    "reduce visceral/belly fat": "visceral-fat", "belly / abdominal fat loss": "visceral-fat",
    "cutting body fat while keeping muscle (recomp / contest prep)": "recomp",
    "keep or build muscle while cutting": "recomp", "lean muscle gain or retention while dieting": "recomp",
    "lean muscle gain or retention": "recomp", "keeping muscle while losing fat": "recomp",
    "breaking a weight-loss plateau after tirzepatide or semaglutide": "plateau",
    "breaking a weight-loss plateau": "plateau",
    "maintaining weight after a prior loss (low-dose maintenance)": "weight-maintenance",
    "low-dose maintenance or microdosing for general health / inflammation": "weight-maintenance",
    "quieting food noise / appetite control": "appetite-control",
    "quieting food noise / binge and snack control": "appetite-control",
    "stronger fullness / portion control at meals": "appetite-control", "appetite control": "appetite-control",
    "appetite suppression / weight loss": "appetite-control",
    "appetite boost for bulking / eating more": "appetite-increase",
    "extra weight loss on top of a glp-1 (stacking)": "glp1-stack",
    "losing weight without pushing the glp-1 dose higher (fewer gi side effects)": "glp1-stack",
    "add-on to a glp-1 or diet cut": "glp1-stack",
    # muscle / performance
    "muscle gain (bodybuilding)": "muscle-gain", "lean muscle gain": "muscle-gain",
    "faster recovery from hard training": "training-recovery", "faster recovery from training": "training-recovery",
    "more endurance / exercise capacity": "endurance", "more energy and exercise capacity": "endurance",
    # healing
    "faster healing of tendon, ligament or joint injury": "injury-healing",
    "faster recovery of tendons, joints or injured tissue (injectable use)": "injury-healing",
    "joint or cartilage pain relief (osteoarthritis)": "joint-pain",
    "less joint (knee/hip) pain with weight loss": "joint-pain",
    "reducing inflammation or joint pain (microdose use)": "joint-pain",
    "faster healing of scars, wounds, acne marks or stretch marks": "wound-scar",
    "less chronic pain": "chronic-pain",
    "recovery after surgery": "post-surgery",
    "healing a muscle tear or strain": "injury-healing",
    "joint pain or arthritis": "joint-pain", "joint pain or inflammation": "joint-pain",
    "general workout recovery / injury prevention": "training-recovery",
    "general workout recovery / less soreness": "training-recovery",
    "post-workout inflammation / recovery": "training-recovery",
    "an old or chronic injury that never fully healed": "chronic-injury",
    "faster recovery from a tendon or ligament injury (tennis elbow, achilles, rotator cuff, patellar tendinitis)": "injury-healing",
    "faster recovery from a tendon, ligament, or muscle injury": "injury-healing",
    "faster recovery from a tendon or ligament injury": "injury-healing",
    "gut issues — ibs, leaky gut, ulcers, crohn's / colitis, bloating or food sensitivities": "gut",
    "gut issues (from the bpc-157 component)": "gut",
    "gut inflammation — ibs, ibd, crohn's, colitis, leaky gut": "gut",
    "gut infections or dysbiosis — sibo, candida": "gut-infection",
    "brain, nerve or mood issues — concussion, nerve pain, anxiety / depression": "brain-injury",
    "flexibility, mobility, or stiffness": "mobility",
    "hair regrowth or hair health": "hair",
    "skin conditions — eczema, psoriasis, rosacea, acne": "skin-condition",
    "skin problems — acne, rosacea, psoriasis, fungal skin infections": "skin-condition",
    "allergies, histamine or mast-cell issues (mcas)": "allergy-mcas",
    "autoimmune flares or general body-wide inflammation": "autoimmune",
    "sinus or respiratory inflammation": "sinus-respiratory", "sinus or respiratory infections": "sinus-respiratory",
    "wound healing or infection": "wound-scar", "a wound or ulcer that won't heal": "wound-scar",
    "chronic or 'stealth' infection — lyme, mold, biofilm, co-infections": "infection",
    "getting sick less often / immune support": "immune",
    "long covid or post-viral symptoms": "long-covid",
    # metabolic
    "lowering blood sugar or a1c": "blood-sugar",
    "lowering blood sugar or a1c (diabetes, prediabetes, insulin resistance)": "blood-sugar",
    "lowering blood sugar / insulin resistance": "blood-sugar",
    "better blood sugar control or insulin sensitivity": "blood-sugar",
    "better blood sugar / metabolic markers": "blood-sugar",
    "better cholesterol or blood sugar markers": "lipids",
    "pcos-related weight and insulin issues": "pcos",
    "reduce liver fat (fatty liver)": "liver-fat",
    "heart or kidney protection": "cardio-kidney",
    # cravings
    "cutting alcohol cravings or drinking less": "cravings",
    "cutting alcohol or nicotine cravings": "cravings",
    "recovery from alcohol or drug use, fewer cravings": "cravings",
    "reduce cravings / help tapering off benzos or alcohol": "withdrawal",
    "easier alcohol or opioid withdrawal": "withdrawal",
    # sleep
    "deeper, more restorative sleep": "deeper-sleep",
    "deeper sleep or a normalized sleep-wake cycle": "deeper-sleep",
    "better sleep": "deeper-sleep", "easier sleep": "deeper-sleep",
    "fall asleep faster": "fall-asleep",
    # cognitive
    "sharper focus and concentration": "focus", "calm focus without sedation": "focus",
    "better memory and learning": "memory", "memory, focus or 'brain fog'": "brain-fog",
    "less brain fog / mental fatigue": "brain-fog", "clearer thinking, less brain fog": "brain-fog",
    "less brain fog (e.g. after covid)": "brain-fog",
    "slowing memory loss / cognitive decline": "cognitive-decline",
    "recovery after concussion or head injury": "brain-injury",
    "recovery after concussion, head injury or stroke": "brain-injury",
    "recovery after stroke, concussion or head injury": "brain-injury",
    "long-term brain health / neuroprotection": "neuroprotection",
    "more motivation and drive": "motivation",
    "better verbal fluency / creativity": "verbal-creativity",
    # mood
    "lift in mood": "mood", "better mood": "mood", "better mood or motivation": "mood",
    "lift in depression / low mood": "mood", "better mood / less depression": "mood",
    "better mood and energy the next day": "mood",
    "less anxiety and stress": "anxiety", "lower stress or anxiety": "anxiety",
    "less stress / lower cortisol": "anxiety",
    "feeling calmer or more at ease in social situations": "social-ease",
    # energy / longevity
    "more daily energy, less fatigue": "energy", "more daily energy / less fatigue": "energy",
    "more daily energy": "energy", "energy and 'feeling younger' (anti-aging)": "energy",
    "general longevity / anti-aging": "longevity", "general longevity / 'mitochondrial health'": "longevity",
    "general longevity / 'telomere' anti-aging": "longevity", "'nad+ boosting' / longevity": "longevity",
    "general 'anti-aging' / feeling younger (injectable use)": "longevity",
    "fewer infections / immune support": "immune", "fewer colds / immune support": "immune",
    "long covid or chronic fatigue symptoms": "long-covid",
    "bone density": "bone-density", "bone density support": "bone-density",
    # appearance
    "skin, hair and 'anti-aging' appearance": "skin-aging", "skin, hair and nail quality": "skin-aging",
    "smoother skin texture / fewer fine lines and wrinkles": "skin-aging",
    "better skin or hair appearance": "skin-aging",
    "hair regrowth or thicker hair (scalp)": "hair",
    "more even skin tone / less redness or sun damage": "skin-tone",
    "more even skin tone (covering scars, vitiligo, patchiness)": "skin-tone",
    "darker tan with less sun or sunbed exposure": "tan",
    "being able to tan without burning (fair skin)": "sun-tolerance",
    # sexual / hormonal
    "stronger sexual desire / libido (men)": "libido", "stronger sexual desire / libido (women)": "libido",
    "stronger sexual desire or arousal": "libido", "stronger sexual desire or erections": "libido",
    "restoring desire lost on ssris, trt or glp-1 drugs": "libido",
    "firmer or more reliable erections": "erections",
    "more intense arousal or orgasm": "orgasm", "more intense orgasm or sexual satisfaction": "orgasm",
    "back-up or add-on when viagra/cialis are not enough": "ed-adjunct",
    "higher natural testosterone": "testosterone",
    "restoring hormone function after a steroid cycle or coming off trt": "pct",
    "fertility (sperm count / ovulation)": "fertility",
    "closer bonding or intimacy with a partner": "bonding",
    # labs / other
    "raise igf-1 on bloodwork (gh optimization)": "igf1", "gh/igf-1 increase without injections": "igf1",
    "amplify a ghrp/ipamorelin pulse (stacking)": "igf1",
    "annual 'reset' course (khavinson-style)": "annual-reset",
    # newly included compounds
    "falling asleep faster": "fall-asleep", "deeper or less interrupted sleep": "deeper-sleep",
    "better sleep on nights with stress or jet lag": "deeper-sleep", "less next-day fatigue": "energy",
    "lower stress / cortisol": "anxiety", "darker tan with less sun exposure": "tan",
    "tanning without the nausea, erections or appetite loss of melanotan ii": "tan",
    "sun sensitivity / burning less easily": "sun-tolerance", "more even skin tone": "skin-tone",
    "keeping testicular size and function while on trt": "trt-support",
    "preserving fertility / sperm count on trt": "trt-support",
    "restarting natural testosterone after a cycle": "pct",
    "higher natural testosterone without trt": "testosterone",
    "reducing liver fat / fatty liver": "liver-fat", "reducing liver fat / fatty liver (masld/mash)": "liver-fat",
    "switching or stacking when tirzepatide stalls": "plateau",
    "trying a glucagon-receptor compound after glp-1 or gip plateau": "plateau",
    "higher energy burn (glucagon effect)": "fat-loss", "stacking with tirzepatide for extra loss": "glp1-stack",
    "preferring a daily dose that can be adjusted day to day": "glp1-alternative",
    "cheaper legal alternative to weekly glp-1s": "glp1-alternative",
    "non-injectable alternative to glp-1s": "glp1-alternative",
    "hold weight after stopping a glp-1": "weight-maintenance",
    "long-term brain health / neurogenesis": "neuroprotection", "lift in mood / less depression": "mood",
    "less anxiety": "anxiety", "better sleep / circadian rhythm": "deeper-sleep",
    "better memory and focus": "memory", "slowing brain aging / longevity": "neuroprotection",
    "stress resilience": "anxiety", "brain / cognitive protection": "neuroprotection",
    "brain protection / cognition": "neuroprotection",
    "sustained igf-1 elevation with weekly dosing": "igf1", "gut/stomach healing": "gut",
    "strong gh pulse for lean muscle gain": "muscle-gain", "raise igf-1 without the hunger of ghrp-6": "igf1",
    "strongest gh pulse for muscle gain and strength": "muscle-gain",
    "heart health / cardioprotection": "cardio-kidney", "heart protection": "cardio-kidney",
    "heart health or heart-failure symptoms": "cardio-kidney", "kidney function": "cardio-kidney",
    "short 'kickstart' before switching to another ghrp": "igf1",
    "joint or cartilage pain relief": "joint-pain", "joint pain or osteoarthritis": "joint-pain",
    "fat loss without gh-type side effects": "fat-loss", "metabolic/blood-sugar support": "blood-sugar",
    "better insulin sensitivity or metabolic health": "blood-sugar",
    "skin brightening / lightening": "skin-brightening", "'detox' or liver support": "detox-liver",
    "hangover or post-drinking recovery": "hangover", "antioxidant / longevity": "longevity",
    "recover from a lingering illness (long covid, ebv, mono)": "long-covid",
    "fewer infections / general immune support": "immune",
    "chronic lyme, mold or cirs symptoms": "infection",
    "calm an overactive or autoimmune immune system": "autoimmune",
    "cancer treatment adjunct": "cancer-adjunct", "hepatitis b or c": "hepatitis",
    "more energy / less chronic fatigue": "energy", "weight loss / appetite suppression": "fat-loss",
    "less 'food noise' or cravings": "appetite-control", "more energy or focus": "energy",
    "'mitochondrial repair' / general longevity": "longevity",
    "better exercise performance and recovery": "endurance",
    "eye health (macular degeneration)": "eye-health",
    "stack partner with mots-c": "longevity", "'exercise in a pill' on rest days": "endurance",
    "clear senescent 'zombie' cells / longevity": "longevity", "better skin or hair": "skin-aging",
    "feeling younger / more energy": "energy",
    "nerve pain or neuropathy (small-fiber, diabetic, chemo-related)": "nerve-pain",
    "burning, tingling, or numbness in hands and feet": "nerve-pain",
    "long covid, dysautonomia, or pots symptoms": "long-covid",
    "autoimmune or inflammatory pain (e.g. sarcoidosis)": "autoimmune",
    "nerve repair after an injury or surgery": "injury-healing",
    "general inflammation / metabolic health": "autoimmune",
}

# ------------------------------------------------------------------ adverse effects
# Universal: asked for EVERY compound. Route-gated ones are shown only when that route is selected.
UNIVERSAL_AE = OrderedDict([
    ("headache",            "Headache"),
    ("nausea",              "Nausea"),
    ("vomiting",            "Vomiting"),
    ("dizziness",           "Dizziness or lightheadedness"),
    ("fatigue",             "Fatigue / low energy"),
    ("insomnia",            "Trouble sleeping"),
    ("vivid-dreams",        "Vivid dreams"),
    ("flushing",            "Flushing or feeling warm"),
    ("anxiety-jittery",     "Anxiety, restlessness or feeling wired"),
    ("low-mood",            "Low mood or irritability"),
    ("appetite-change",     "Appetite change"),
    ("injection-site",      "Injection-site reaction (redness, itching, lump, bruising)"),   # route: injectable
    ("nasal-irritation",    "Nasal irritation, burning or sneezing"),                        # route: intranasal
    ("tolerance",           "Effect faded with repeated use"),
    ("no-effect",           "No noticeable effect at all"),
])

AE_GROUP = OrderedDict([
    # GI
    ("constipation",        "Constipation"),
    ("diarrhea",            "Diarrhea or loose stools"),
    ("reflux-bloating",     "Acid reflux, bloating, burping or sulfur burps"),
    ("stomach-pain",        "Stomach pain or cramping"),
    ("early-fullness",      "Getting full very fast / eating too little"),
    ("gallbladder",         "Gallbladder pain / gallstones"),
    ("pancreatitis-scare",  "Severe stomach pain (pancreatitis scare)"),
    # metabolic
    ("hypoglycemia",        "Low blood sugar episodes (shaky, sweaty, weak)"),
    ("high-blood-sugar",    "Elevated fasting blood sugar or insulin resistance on labs"),
    ("hunger",              "Intense hunger or rebound cravings"),
    ("unwanted-weight-gain","Unwanted weight gain"),
    # GH-axis
    ("water-retention",     "Water retention, bloating or puffy face/hands"),
    ("joint-pain",          "Joint pain or stiffness"),
    ("carpal-tunnel",       "Tingling or numb hands / fingers"),
    ("swollen-extremities", "Swollen ankles or feet"),
    ("skin-tags-moles",     "New skin tags or moles"),
    ("low-thyroid",         "Low-thyroid symptoms"),
    ("muscle-cramps",       "Muscle cramps or aches"),
    # cardio
    ("palpitations",        "Racing heart, palpitations or higher resting heart rate"),
    ("blood-pressure",      "Blood pressure changes"),
    ("chest-tightness",     "Chest tightness or pressure"),
    # neuro / mood
    ("brain-fog",           "Brain fog or mental fatigue"),
    ("drowsiness",          "Drowsiness or feeling flat / too calm"),
    ("grogginess",          "Next-day grogginess or hangover feeling"),
    ("paradoxical",         "Opposite of intended effect (e.g. more anxious, worse sleep)"),
    ("emotional",           "Feeling weepy or emotionally raw"),
    ("agitation",           "Agitation or feeling overstimulated"),
    # skin / hair
    ("hair-shedding",       "Hair shedding"),
    ("moles-freckles",      "New or darkening moles / freckles"),
    ("uneven-darkening",    "Uneven skin darkening"),
    ("skin-irritation",     "Skin irritation, rash, hives or breakouts"),
    ("skin-staining",       "Blue-green staining or residue on skin"),
    ("dysesthesia",         "Skin tingling, burning or sunburn-like sensitivity"),
    ("hyperpigmentation",   "Skin, gum or mole darkening"),
    ("injury-worse",        "Pain or inflammation got worse at the injury"),
    ("flu-like",            "Flu-like or achy feeling for a day or two"),
    ("condition-flare",     "Flare-up of the condition being treated"),
    ("herx",                "'Herx' / die-off reaction (fatigue, aches, chills)"),
    ("prolactin",           "Low libido or nipple tenderness"),
    ("sweating",            "Sweating"),
    ("skin-lightening",     "Unwanted skin lightening"),
    ("dry-mouth",           "Dry mouth"),
    ("facial-volume-loss",  "Facial volume loss or loose skin"),
    ("acne",                "Acne or oily skin"),
    # sexual / hormonal
    ("erections-unwanted",  "Unwanted or prolonged erections"),
    ("mood-swings",         "Mood swings"),
    # muscle
    ("muscle-loss",         "Muscle loss or weakness"),
    # misc
    ("alcohol-sensitivity", "Alcohol hitting harder"),
    ("taste-changes",       "Taste changes"),
    ("cramping-women",      "Cramping (women)"),
    ("dyspnea-rare",        "Trouble swallowing (rare)"),
    ("injection-pain-severe","Severe stinging or pain at the injection site"),
])

def norm(s):
    s = s.lower().strip()
    s = re.sub(r"\s+", " ", s)
    return s

# Substring rules for AEs (checked in order; first match wins). Map -> ae id or "universal:<id>".
AE_RULES = [
    # universal
    (r"^headache", "u:headache"),
    (r"^nausea", "u:nausea"),
    (r"^vomiting", "u:vomiting"),
    (r"dizziness|lightheaded|vertigo", "u:dizziness"),
    (r"fatigue|tiredness|lethargy|low energy|wiped out|drained|feeling flat.*day|tired", "u:fatigue"),
    (r"trouble sleeping|insomnia|disrupted sleep|sleep changes|restlessness or trouble sleeping|wired or trouble sleeping", "u:insomnia"),
    (r"vivid dreams|nightmares", "u:vivid-dreams"),
    (r"flushing|feeling hot|feeling warm|head rush|skin warmth|sweating right after", "u:flushing"),
    (r"anxiety|jittery|wired|restless", "u:anxiety-jittery"),
    (r"low mood|irritab|flat motivation|anhedonia|short temper", "u:low-mood"),
    (r"appetite change|reduced appetite|loss of appetite|appetite changes", "u:appetite-change"),
    (r"injection-site|injection site|at the injection|redness or bump|welts or itching|welt|bruising at injection", "u:injection-site"),
    (r"nasal|stuffy or runny nose", "u:nasal-irritation"),
    (r"tolerance|effect fad|wearing off|stops working|fades with", "u:tolerance"),
    (r"no noticeable effect", "u:no-effect"),
    # GI
    (r"^constipation", "constipation"),
    (r"diarrhea|loose stools", "diarrhea"),
    (r"reflux|bloating|burp|upset stomach|stomach upset", "reflux-bloating"),
    (r"stomach cramp|stomach pain|cramping or diarrhea", "stomach-pain"),
    (r"full very fast|cannot finish|under-eating|eating too little", "early-fullness"),
    (r"gallbladder|gallstone", "gallbladder"),
    (r"pancreatitis", "pancreatitis-scare"),
    # metabolic
    (r"low blood sugar|low-blood-sugar|shaky", "hypoglycemia"),
    (r"elevated fasting blood sugar|insulin resistance on labs|hba1c", "high-blood-sugar"),
    (r"intense hunger|rebound hunger|increased hunger|increase in hunger|carb cravings", "hunger"),
    (r"unwanted fat|weight gain", "unwanted-weight-gain"),
    # GH
    (r"water retention|puffy", "water-retention"),
    (r"joint pain|stiffness", "joint-pain"),
    (r"tingling or numb|carpal", "carpal-tunnel"),
    (r"swollen ankles|swelling of hands", "swollen-extremities"),
    (r"skin tags", "skin-tags-moles"),
    (r"low-thyroid", "low-thyroid"),
    (r"muscle cramps|muscle aches", "muscle-cramps"),
    (r"gut/abdominal distension", "reflux-bloating"),
    # cardio
    (r"racing heart|palpitation|pounding heart|resting heart rate", "palpitations"),
    (r"blood pressure", "blood-pressure"),
    (r"chest tightness", "chest-tightness"),
    # neuro
    (r"brain fog|mental fatigue", "brain-fog"),
    (r"drowsiness|too calm|feeling flat|sleepy afterward|daytime sleepiness|daytime drowsiness", "drowsiness"),
    (r"grogginess|hangover", "grogginess"),
    (r"paradoxical|opposite of|worse sleep|instead of sleepy", "paradoxical"),
    (r"weepy|emotionally raw", "emotional"),
    (r"agitation|overstimulated", "agitation"),
    # skin / hair
    (r"hair shedding|hair loss", "hair-shedding"),
    (r"skin, gum, or mole darkening|skin or gum darkening", "hyperpigmentation"),
    (r"got worse at the injury", "injury-worse"),
    (r"flu-like", "flu-like"),
    (r"flare-up of the condition|flare of an autoimmune", "condition-flare"),
    (r"herx|die-off", "herx"),
    (r"prolactin|nipple", "prolactin"),
    (r"^sweating", "sweating"),
    (r"skin lightening", "skin-lightening"),
    (r"dry mouth", "dry-mouth"),
    (r"low-grade fever|cold-like", "flu-like"),
    (r"blood sugar swings", "hypoglycemia"),
    (r"faster heart rate", "palpitations"),
    (r"mood changes", "u:low-mood"),
    (r"sleep disruption", "u:insomnia"),
    (r"increase in nerve pain", "injury-worse"),
    (r"moles|freckles", "moles-freckles"),
    (r"uneven darkening", "uneven-darkening"),
    (r"rash|hives|allergic|skin irritation|breakouts", "skin-irritation"),
    (r"blue-green|staining", "skin-staining"),
    (r"dysesthesia|sunburn-like", "dysesthesia"),
    (r"facial volume|ozempic face|loose skin", "facial-volume-loss"),
    (r"acne|oily skin", "acne"),
    # sexual
    (r"erections", "erections-unwanted"),
    (r"mood swings", "mood-swings"),
    # muscle
    (r"muscle loss|weakness", "muscle-loss"),
    # misc
    (r"alcohol hitting", "alcohol-sensitivity"),
    (r"taste", "taste-changes"),
    (r"cramping \(women\)", "cramping-women"),
    (r"trouble swallowing", "dyspnea-rare"),
    (r"stinging|worst of any peptide|burning or pain at the injection", "injection-pain-severe"),
    (r"yawning|stretching", "u:fatigue"),
    (r"temporary increase in hair shedding", "hair-shedding"),
]

def map_ae(phrase):
    p = norm(phrase)
    for pat, target in AE_RULES:
        if re.search(pat, p):
            return target
    return None

# ------------------------------------------------------------------ routes / frequency
ROUTE_MAP = {
    "subcutaneous": "subcutaneous", "subcutaneous injection": "subcutaneous", "subcutaneous (rare)": "subcutaneous",
    "intramuscular": "intramuscular", "intramuscular (less common)": "intramuscular",
    "intranasal": "intranasal",
    "oral": "oral", "oral (compounded troche/tablet, uncommon)": "oral", "oral (tablet or sublingual troche)": "oral",
    "oral / troche": "oral", "oral (less common)": "oral", "sublingual": "oral", "sublingual / buccal troche": "oral",
    "oral (usually nr/nmn precursors instead)": "oral",
    "topical": "topical", "topical (dmso transdermal)": "topical", "topical (joint creams, rare)": "topical",
    "intradermal (microneedling / mesotherapy)": "topical",
    "intravenous": "intravenous", "intravenous (clinic)": "intravenous", "intravenous (trials only)": "intravenous",
    "intra-articular": "intramuscular",
}
ROUTES = OrderedDict([
    ("subcutaneous", "Subcutaneous injection"),
    ("intramuscular", "Intramuscular injection"),
    ("intranasal", "Nasal spray / drops"),
    ("oral", "Oral / sublingual / troche"),
    ("topical", "Topical / transdermal"),
    ("intravenous", "Intravenous (clinic)"),
])

FREQ = OrderedDict([
    ("multiple-daily", "More than once a day"),
    ("daily",          "Once a day"),
    ("5-on-2-off",     "5 days on / 2 days off"),
    ("every-other-day","Every other day"),
    ("2-3-weekly",     "2–3 times a week"),
    ("weekly",         "About once a week"),
    ("less-than-weekly","Less than weekly"),
    ("as-needed",      "As needed / on demand"),
    ("cycled",         "In cycles (weeks on, weeks off)"),
])
FREQ_RULES = [
    (r"twice|2x|3x|three times|2 times per day|split dose|multiple", "multiple-daily"),
    (r"5 days on", "5-on-2-off"),
    (r"every other day|every third day", "every-other-day"),
    (r"every 5 days", "weekly"),
    (r"every other week", "less-than-weekly"),
    (r"training days only", "as-needed"),
    (r"2 to 3 times per week|2-3x/week|2-3 times|few nights per week|about once a week or less", "2-3-weekly"),
    (r"every 10-14 days|less than weekly", "less-than-weekly"),
    (r"^weekly|once weekly|once a week", "weekly"),
    (r"as needed|on demand|task days|bad", "as-needed"),
    (r"cycle|seasonal|loading then|courses per year", "cycled"),
    (r"daily|nightly|once a day|every day", "daily"),
]
def map_freq(phrase):
    p = norm(phrase)
    for pat, t in FREQ_RULES:
        if re.search(pat, p):
            return t
    return None

# ------------------------------------------------------------------ mechanism classes
CLASS_MAP = {
    "GLP-1/GIP/glucagon triple agonist": "incretin", "GLP-1/GIP dual agonist": "incretin",
    "GLP-1 mono-agonist": "incretin", "long-acting amylin analog": "incretin",
    "GLP-1/glucagon dual agonist": "incretin",
    "GH secretagogue (ghrelin mimetic)": "gh-secretagogue", "GHRH + GHS blend": "gh-secretagogue",
    "GHRH analogue": "gh-secretagogue", "Exogenous growth hormone": "gh-secretagogue",
    "GH fragment": "metabolic", "Growth hormone fragment (lipolytic)": "metabolic",
    "NAD+ precursor / mitochondrial cofactor": "metabolic",
    "Mitochondrial-derived peptide / AMPK activator": "metabolic",
    "NNMT inhibitor (small molecule, NAD+/metabolic)": "metabolic",
    "Pineal / thymic bioregulator peptide (Khavinson class)": "metabolic",
    "melanocortin agonist": "sexual-hormonal",
    "HPG-axis stimulator (GnRH/testosterone-releasing)": "sexual-hormonal",
    "oxytocin-receptor agonist / social neuropeptide": "neuro",
    "copper tripeptide / skin-remodeling peptide": "tissue-repair",
    "Sleep/stress-regulating neuropeptide": "neuro",
    "Tuftsin-analog anxiolytic neuropeptide (GABA/enkephalin-modulating)": "neuro",
    "HGF/c-Met-potentiating angiotensin IV analog (synaptogenic nootropic)": "neuro",
    "Neurotrophic peptide mixture (porcine brain-derived)": "neuro",
    "Neurotrophic peptide mixture (porcine brain-derived, BDNF/CNTF-like activity)": "neuro",
    "CNTF-mimetic neurogenic peptide": "neuro",
    "Khavinson short-peptide bioregulator (neuro)": "neuro",
    "sleep neuropeptide": "neuro",
    "Antioxidant tripeptide": "metabolic",
    "Thymic immune-modulating peptide": "metabolic",
    "Triple monoamine reuptake inhibitor (small-molecule appetite suppressant)": "metabolic",
    "Cardiolipin-binding mitochondrial peptide": "metabolic",
    "Mitochondrial-derived peptide / cytoprotective": "metabolic",
    "ERR agonist (small-molecule exercise mimetic)": "metabolic",
    "Senolytic peptide (FOXO4-p53 disruptor)": "metabolic",
}
CLASSES = OrderedDict([
    ("incretin",        "GLP-1 / incretin agonists"),
    ("gh-secretagogue", "Growth hormone axis"),
    ("tissue-repair",   "Tissue repair / healing"),
    ("neuro",           "Nootropic / mood / sleep"),
    ("metabolic",       "Metabolic / longevity"),
    ("sexual-hormonal", "Sexual function / hormonal"),
])
EXCLUDE_IDS = set()

def map_class(label):
    if label in CLASS_MAP:
        return CLASS_MAP[label]
    l = label.lower()
    if "anti-inflammatory tripeptide" in l or "antimicrobial" in l or "tissue-protective" in l:
        return "tissue-repair"
    if "monoamine" in l or "mitochondrial" in l or "senolytic" in l or "err agonist" in l:
        return "metabolic"
    if "cntf" in l or "khavinson" in l or "sleep" in l:
        return "neuro"
    if "melanocortin" in l and "neuropeptide" in l:
        return "neuro"
    if "tissue" in l or "repair" in l or "healing" in l:
        return "tissue-repair"
    return None

def slug(name):
    s = name.lower()
    s = re.sub(r"\(.*?\)", "", s)
    s = re.sub(r"[^a-z0-9]+", "-", s).strip("-")
    return s

# ------------------------------------------------------------------ main
def main():
    src = json.load(open(os.environ.get("PA_RESEARCH", os.path.expanduser("~/privateanecdata-research/taxonomy.research.json"))))
    unmapped_goals, unmapped_ae, unmapped_freq, unmapped_class = Counter(), Counter(), Counter(), Counter()
    out = []
    seen = set()
    for fam in src["families"]:
        for c in fam["compounds"]:
            if not c.get("includeInV1"):
                continue
            if slug(c["canonicalName"]) in EXCLUDE_IDS or slug(c["canonicalName"]) in seen:
                continue
            seen.add(slug(c["canonicalName"]))
            cls = map_class(c["mechanismClass"])
            if cls is None:
                unmapped_class[c["mechanismClass"]] += 1
                cls = "UNMAPPED"
            goals = []
            for g in c["goals"]:
                gid = GOAL_MAP.get(norm(g))
                if gid is None:
                    unmapped_goals[g] += 1
                elif gid not in goals:
                    goals.append(gid)
            aes, uni = [], []
            for a in c["adverseEffects"]:
                t = map_ae(a)
                if t is None:
                    unmapped_ae[a] += 1
                elif t.startswith("u:"):
                    uni.append(t[2:])
                elif t not in aes:
                    aes.append(t)
            routes = []
            for r in c["routes"]:
                rid = ROUTE_MAP.get(norm(r))
                if rid and rid not in routes:
                    routes.append(rid)
            freqs = []
            for f in c["frequencyOptions"]:
                fid = map_freq(f)
                if fid is None:
                    unmapped_freq[f] += 1
                elif fid not in freqs:
                    freqs.append(fid)
            out.append(OrderedDict([
                ("id", slug(c["canonicalName"])),
                ("label", c["canonicalName"]),
                ("aliases", c["aliases"]),
                ("class", cls),
                ("goals", goals),
                ("adverseEffects", aes),
                ("routes", routes),
                ("doseBands", c["doseBands"]),
                ("frequency", freqs),
                # Regulatory and anti-doping status, dose-band rationale and research notes stay in
                # research/ and are never part of the frozen schema: the site characterises no
                # compound's legal or WADA status, and a status change must not be a schema change.
                ("humanEvidence", c["humanEvidence"]),
            ]))

    print(f"compounds: {len(out)}")
    for name, ctr in (("GOALS", unmapped_goals), ("ADVERSE EFFECTS", unmapped_ae),
                      ("FREQUENCY", unmapped_freq), ("CLASS", unmapped_class)):
        if ctr:
            print(f"\nUNMAPPED {name}:")
            for k, v in ctr.most_common():
                print(f"  {v}  {k}")

    # class membership
    members = {cid: [c["id"] for c in out if c["class"] == cid] for cid in CLASSES}
    singletons = [cid for cid, m in members.items() if len(m) == 1]
    if singletons:
        print(f"\nWARNING singleton classes (rollup would be a singleton): {singletons}")

    def vocab(pairs):
        return [OrderedDict([("id", k), ("label", v)]) for k, v in pairs]
    shared = OrderedDict([
        ("sourceChannel", vocab([
            ("retail-pharmacy", "Retail pharmacy (brand product, prescription)"),
            ("503a-compounder", "Compounding pharmacy"),
            ("telehealth-compounded", "Telehealth or clinic (compounded)"),
            ("domestic-rc-vendor", "Domestic research-chemical vendor"),
            ("overseas-vendor", "Overseas vendor"),
            ("another-person", "From another person"),
            ("unknown", "Don't know"),
            ("other", "Other (not listed)"),
        ])),
        ("titration", vocab([
            ("no-change", "Stayed at the same dose"),
            ("stepped-up", "Stepped the dose up over time"),
            ("stepped-down", "Stepped the dose down over time"),
            ("cycled", "Cycled on and off"),
            ("other", "Other (not listed)"),
        ])),
        ("duration", vocab([
            ("under-2wk", "Under 2 weeks"),
            ("2-4wk", "2 to 4 weeks"),
            ("1-3mo", "1 to 3 months"),
            ("3-6mo", "3 to 6 months"),
            ("6-12mo", "6 to 12 months"),
            ("over-12mo", "Over 12 months"),
        ])),
        ("purityTested", vocab([
            ("no", "No, did not test"),
            ("yes-matched", "Yes — result matched the label"),
            ("yes-did-not-match", "Yes — result did not match the label"),
            ("yes-unsure", "Yes — unsure how to read the result"),
            ("dont-know", "Don't know"),
        ])),
        ("reconstitution", vocab([
            ("bac-water-refrigerated", "Bacteriostatic water, kept refrigerated"),
            ("bac-water-room-temp", "Bacteriostatic water, kept at room temperature"),
            ("sterile-water", "Sterile water"),
            ("pre-mixed-or-pen", "Came pre-mixed or as a pen"),
            ("no-reconstitution", "No reconstitution (oral, nasal, topical)"),
            ("other", "Other (not listed)"),
        ])),
        ("outcome", vocab([
            ("no-change", "No change"),
            ("slight", "Slight improvement"),
            ("moderate", "Moderate improvement"),
            ("large", "Large improvement"),
        ])),
        ("status", vocab([
            ("still-taking", "Still taking it"),
            ("completed-planned-course", "Finished a planned course"),
            ("stopped-under-2wk", "Stopped within 2 weeks"),
            ("stopped-2-6wk", "Stopped after 2 to 6 weeks"),
            ("stopped-6-12wk", "Stopped after 6 to 12 weeks"),
            ("stopped-over-12wk", "Stopped after more than 12 weeks"),
        ])),
        ("stopReason", vocab([
            ("achieved-goal", "Got what I wanted from it"),
            ("no-effect", "It wasn't doing anything"),
            ("adverse-effect", "Side effects"),
            ("cost", "Cost"),
            ("supply", "Couldn't get more"),
            ("safety-concern", "Worried about safety"),
            ("other", "Other (not listed)"),
        ])),
        ("onset", vocab([
            ("first-days", "In the first few days"),
            ("first-2wk", "In the first 2 weeks"),
            ("2-6wk", "Between 2 and 6 weeks"),
            ("after-6wk", "After 6 weeks"),
            ("unsure", "Not sure"),
        ])),
        ("dechallenge", vocab([
            ("resolved", "Went away after stopping"),
            ("did-not-resolve", "Did not go away after stopping"),
            ("still-taking", "Haven't stopped"),
            ("unsure", "Not sure"),
        ])),
        ("ageBand", vocab([
            ("18-24", "18–24"), ("25-34", "25–34"), ("35-44", "35–44"),
            ("45-54", "45–54"), ("55-64", "55–64"), ("65+", "65 or over"),
        ])),
        ("sex", vocab([
            ("male", "Male"), ("female", "Female"), ("prefer-not", "Prefer not to say"),
        ])),
    ])
    taxonomy = OrderedDict([
        ("version", "0.1-draft"),
        ("shared", shared),
        ("compounds", out),
        ("classes", [OrderedDict([("id", cid), ("label", lbl), ("members", members[cid])]) for cid, lbl in CLASSES.items()]),
        ("goals", [OrderedDict([("id", k), ("label", v)]) for k, v in GOALS.items()]),
        ("universalAdverseEffects", [OrderedDict([("id", k), ("label", v)]) for k, v in UNIVERSAL_AE.items()]),
        ("adverseEffects", [OrderedDict([("id", k), ("label", v)]) for k, v in AE_GROUP.items()]),
        ("routes", [OrderedDict([("id", k), ("label", v)]) for k, v in ROUTES.items()]),
        ("frequency", [OrderedDict([("id", k), ("label", v)]) for k, v in FREQ.items()]),
    ])
    json.dump(taxonomy, open("spec/taxonomy.v1.json", "w"), indent=1)
    print("\nwrote spec/taxonomy.v1.json")
    for cid, lbl in CLASSES.items():
        print(f"  {cid:<16} {len(members[cid]):>2}  {', '.join(members[cid])}")

if __name__ == "__main__":
    main()
