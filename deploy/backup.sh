#!/usr/bin/env sh
# Encrypted backup of the submission store. Run from cron as the service user.
#
#   PA_BACKUP_KEY=<gpg key id or fingerprint> PA_BACKUP_DIR=/srv/private-anecdata/backups sh deploy/backup.sh
#
# The backup is a consistent SQLite copy (`.backup`, safe under WAL), encrypted to a public key
# whose private half is NOT on this host, so the host can make backups it cannot read. Retention
# is the number of days in PA_BACKUP_KEEP_DAYS and must match what docs/LEGAL-PROCESS.md states.
# A backup contains exactly the store's fields — the same coarsened rows, salts and log — and
# nothing else; there is nothing else on the host to back up.
set -eu
DB="${PA_DB_PATH:-/srv/private-anecdata/data/reports.db}"
OUT="${PA_BACKUP_DIR:-/srv/private-anecdata/backups}"
KEEP="${PA_BACKUP_KEEP_DAYS:-30}"
: "${PA_BACKUP_KEY:?set PA_BACKUP_KEY to the recipient key id}"
mkdir -p "$OUT"; chmod 700 "$OUT"
TMP=$(mktemp "$OUT/.snapshot.XXXXXX")
trap 'rm -f "$TMP"' EXIT
sqlite3 "$DB" ".backup '$TMP'"
STAMP=$(date -u +%Y-%m-%d)
gpg --batch --yes --trust-model always -r "$PA_BACKUP_KEY" -o "$OUT/reports-$STAMP.sqlite.gpg" -e "$TMP"
rm -f "$TMP"
find "$OUT" -name 'reports-*.sqlite.gpg' -mtime +"$KEEP" -delete
echo "backup written: $OUT/reports-$STAMP.sqlite.gpg (keeping $KEEP days)"
