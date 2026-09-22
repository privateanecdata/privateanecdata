#!/usr/bin/env sh
# Everything that must pass before a build is trusted. Run locally before a release; CI runs it
# on every push. Exits non-zero on the first failure.
set -eu
cd "$(dirname "$0")/.."
echo "== taxonomy -> schema config -> SCHEMA.md are in sync"
python3 tools/make_schema_config.py >/dev/null
python3 tools/render_schema_md.py >/dev/null
git diff --quiet -- spec/schema.config.json spec/SCHEMA.md || { echo "spec/ derived files are out of date: run the two tools above and commit"; exit 1; }
echo "== pipeline tests"
python3 -m unittest discover -s tools/tests
echo "== synthetic release builds and verifies"
T=$(mktemp -d)
python3 tools/synth_store.py "$T/s.db" --n 1500 --seed 3 >/dev/null
python3 tools/release.py --db "$T/s.db" --id CI-SYNTHETIC --date 2026-12-31 --out "$T/r" >/dev/null 2>&1
python3 tools/verify_release.py "$T/r" --spec spec/RELEASE_SPEC.md --taxonomy spec/taxonomy.v1.json --db "$T/s.db" | tail -1
rm -rf "$T"
echo "== site: one origin, no scripts"
( cd app && npm ci --silent >/dev/null 2>&1 || npm install --silent >/dev/null 2>&1 )
PA_RELEASES_DIR=$(mktemp -d) sh tools/check_origin.sh
echo "== preflight passed"
