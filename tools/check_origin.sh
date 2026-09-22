#!/usr/bin/env sh
# Build the app, start it on a spare port, run the one-origin check, stop it. Non-zero on failure.
# Meant for CI and for the pre-release checklist.
set -eu
cd "$(dirname "$0")/../app"
npm run build >/dev/null
PORT=${PORT:-4399}
PA_RELEASES_DIR="${PA_RELEASES_DIR:-$PWD/../releases}" PA_DB_PATH="${PA_DB_PATH:-$(mktemp -d)/check.db}" PORT=$PORT HOST=127.0.0.1 \
  node dist/server/entry.mjs >/dev/null 2>&1 &
PID=$!
trap 'kill $PID 2>/dev/null || true' EXIT
for i in 1 2 3 4 5 6 7 8 9 10; do curl -sf "http://127.0.0.1:$PORT/" >/dev/null && break; sleep 0.5; done
python3 ../tools/check_origin.py "http://127.0.0.1:$PORT" "$@"
python3 ../tools/check_form.py "http://127.0.0.1:$PORT"
