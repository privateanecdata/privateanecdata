#!/usr/bin/env python3
"""
Build a placeholder schema.config.json with realistic cardinalities so uniqueness.py can be
exercised before the real taxonomy exists. Replace with the real vocabularies once frozen.
"""
import json
import sys

N_COMPOUNDS = 25

compounds = []
for i in range(N_COMPOUNDS):
    n_bands = 4 if i % 3 else 5
    n_goals = 4 + (i % 3)
    n_ae = 6 + (i % 4)
    compounds.append({
        "id": f"c{i:02d}",
        "dose_bands": [f"c{i:02d}-band{b}" for b in range(n_bands)],
        "goals": [f"c{i:02d}-goal{g}" for g in range(n_goals)],
        "adverse_effects": [f"c{i:02d}-ae{a}" for a in range(n_ae)],
    })

shared = {
    "source_channel": {
        "options": ["retail-pharmacy", "503a-compounder", "telehealth-compounded",
                    "domestic-rc-vendor", "overseas-vendor", "another-person", "unknown", "other"],
        "skew": [0.05, 0.10, 0.12, 0.45, 0.20, 0.04, 0.03, 0.01],
    },
    "titration": {
        "options": ["no-change", "stepped-up", "stepped-down", "cycled", "other"],
        "skew": [0.45, 0.35, 0.08, 0.10, 0.02],
    },
    "duration": {
        "options": ["under-2wk", "2-4wk", "1-3mo", "3-6mo", "6-12mo", "over-12mo", "other"],
        "skew": [0.08, 0.18, 0.34, 0.22, 0.12, 0.05, 0.01],
    },
    "purity_tested": {
        "options": ["no", "yes-matched", "yes-did-not-match", "yes-unsure", "dont-know"],
        "skew": [0.70, 0.15, 0.04, 0.03, 0.08],
    },
    "reconstitution": {
        "options": ["bac-water-refrigerated", "bac-water-room-temp", "sterile-water",
                    "pre-mixed", "oral-no-reconstitution", "other"],
        "skew": [0.55, 0.10, 0.08, 0.15, 0.10, 0.02],
    },
    "status": {
        "options": ["still-taking", "stopped-under-2wk", "stopped-2-6wk", "stopped-6-12wk",
                    "stopped-over-12wk", "completed-planned-course"],
        "skew": [0.45, 0.08, 0.12, 0.12, 0.08, 0.15],
    },
    "stop_reason": {
        "options": ["n/a-still-taking", "achieved-goal", "no-effect", "adverse-effect",
                    "cost", "supply", "concern-about-safety", "other"],
        "skew": [0.45, 0.12, 0.15, 0.12, 0.06, 0.05, 0.03, 0.02],
    },
    "age_band": {
        "options": ["18-24", "25-34", "35-44", "45-54", "55-64", "65+"],
        "skew": [0.08, 0.30, 0.32, 0.18, 0.09, 0.03],
    },
    "sex": {
        "options": ["male", "female", "prefer-not"],
        "skew": [0.62, 0.33, 0.05],
    },
    "quarter_started": {
        "options": ["2024Q3", "2024Q4", "2025Q1", "2025Q2", "2025Q3", "2025Q4", "2026Q1", "2026Q2", "2026Q3"],
        "skew": "recent",
    },
    "outcome_scale": {
        "options": ["no-change", "slight", "moderate", "large"],
        "skew": [0.30, 0.25, 0.30, 0.15],
    },
    "universal_adverse_effects": {
        "options": ["injection-site-reaction", "headache", "fatigue", "nausea"],
    },
}

config = {
    "compound_skew": "zipf",
    "compound_zipf_s": 1.1,
    "compounds": compounds,
    "shared_fields": shared,
    "qi_sets": {
        "narrow": ["compound", "age_band", "sex", "quarter_started", "goals",
                   "start_dose", "source_channel", "duration"],
        "narrow-no-quarter": ["compound", "age_band", "sex", "goals",
                              "start_dose", "source_channel", "duration"],
        "demographics-only": ["compound", "age_band", "sex"],
        "broad": ["compound", "age_band", "sex", "quarter_started", "goals",
                  "start_dose", "current_dose", "titration", "source_channel", "duration",
                  "purity_tested", "reconstitution", "status", "stop_reason",
                  "adverse_effects", "outcomes"],
    },
}

out = sys.argv[1] if len(sys.argv) > 1 else "spec/schema.config.placeholder.json"
with open(out, "w") as f:
    json.dump(config, f, indent=1)
print(f"wrote {out}: {N_COMPOUNDS} compounds")
