#!/usr/bin/env python3
"""
Derive spec/schema.config.json (the uniqueness.py input) from spec/taxonomy.v1.json.

This is the REAL schema shape: per-compound single-select goal, per-compound dose bands, no
quarter_started, no location. Skew assumptions are stated inline and are the thing to revise
once real rows exist (run uniqueness.py in `real` mode).
"""
import json
from collections import OrderedDict

tax = json.load(open("spec/taxonomy.v1.json"))

compounds = []
for c in tax["compounds"]:
    compounds.append({
        "id": c["id"],
        "dose_bands": c["doseBands"] or ["band-a", "band-b", "band-c", "band-d"],
        "goals": c["goals"],
        "adverse_effects": c["adverseEffects"],
    })

shared = OrderedDict([
    ("source_channel", {
        "options": ["retail-pharmacy", "503a-compounder", "telehealth-compounded",
                    "domestic-rc-vendor", "overseas-vendor", "another-person", "unknown", "other"],
        "skew": [0.04, 0.10, 0.14, 0.42, 0.20, 0.05, 0.03, 0.02],
    }),
    ("titration", {
        "options": ["no-change", "stepped-up", "stepped-down", "cycled", "other"],
        "skew": [0.45, 0.35, 0.08, 0.10, 0.02],
    }),
    ("duration", {
        "options": ["under-2wk", "2-4wk", "1-3mo", "3-6mo", "6-12mo", "over-12mo"],
        "skew": [0.08, 0.18, 0.34, 0.22, 0.12, 0.06],
    }),
    ("purity_tested", {
        "options": ["no", "yes-matched", "yes-did-not-match", "yes-unsure", "dont-know"],
        "skew": [0.70, 0.15, 0.04, 0.03, 0.08],
    }),
    ("reconstitution", {
        "options": ["bac-water-refrigerated", "bac-water-room-temp", "sterile-water",
                    "pre-mixed-or-pen", "no-reconstitution", "other"],
        "skew": [0.50, 0.08, 0.07, 0.15, 0.18, 0.02],
    }),
    ("status", {
        "options": ["still-taking", "stopped-under-2wk", "stopped-2-6wk", "stopped-6-12wk",
                    "stopped-over-12wk", "completed-planned-course"],
        "skew": [0.45, 0.08, 0.12, 0.12, 0.08, 0.15],
    }),
    ("stop_reason", {
        "options": ["n/a-still-taking", "achieved-goal", "no-effect", "adverse-effect",
                    "cost", "supply", "safety-concern", "other"],
        "skew": [0.45, 0.12, 0.15, 0.12, 0.06, 0.05, 0.03, 0.02],
    }),
    ("age_band", {
        "options": ["18-24", "25-34", "35-44", "45-54", "55-64", "65+"],
        "skew": [0.08, 0.30, 0.32, 0.18, 0.09, 0.03],
    }),
    ("sex", {
        "options": ["male", "female", "prefer-not"],
        "skew": [0.62, 0.33, 0.05],
    }),
    ("outcome_scale", {
        "options": ["no-change", "slight", "moderate", "large"],
        "skew": [0.30, 0.25, 0.30, 0.15],
    }),
    ("universal_adverse_effects", {
        "options": [a["id"] for a in tax["universalAdverseEffects"]],
    }),
])

config = OrderedDict([
    ("_source", "spec/taxonomy.v1.json"),
    ("_note", "Skew weights are pre-launch assumptions. Replace with observed distributions once real rows exist."),
    ("compound_skew", "zipf"),
    ("compound_zipf_s", 1.0),
    ("max_goals", 1),
    ("compounds", compounds),
    ("shared_fields", shared),
    ("qi_sets", OrderedDict([
        # what a detailed public post would reveal
        ("narrow",            ["compound", "age_band", "sex", "goals", "start_dose", "source_channel", "duration"]),
        # what a typical post reveals
        ("plausible-post",    ["compound", "age_band", "sex", "goals", "start_dose"]),
        ("plausible-post-no-dose", ["compound", "age_band", "sex", "goals"]),
        ("demographics-only", ["compound", "age_band", "sex"]),
        # everything the row holds
        ("broad",             ["compound", "age_band", "sex", "goals", "start_dose", "current_dose", "titration",
                               "source_channel", "duration", "purity_tested", "reconstitution", "status",
                               "stop_reason", "adverse_effects", "outcomes"]),
    ])),
])

json.dump(config, open("spec/schema.config.json", "w"), indent=1)
print(f"wrote spec/schema.config.json: {len(compounds)} compounds, "
      f"{sum(len(c['dose_bands']) for c in compounds)} dose bands total, "
      f"{sum(len(c['goals']) for c in compounds)} goal slots")
