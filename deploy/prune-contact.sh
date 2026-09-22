#!/usr/bin/env sh
# Delete contact messages so none is older than 30 days. Run daily from cron as the service user.
#   0 4 * * * sh /srv/private-anecdata/repo/deploy/prune-contact.sh
# A message received on day D is deleted at the D+28 run, i.e. at most ~29 days old.
set -eu
DB="${PA_CONTACT_DB_PATH:-/srv/private-anecdata/data/contact.db}"
[ -f "$DB" ] || exit 0
sqlite3 "$DB" "PRAGMA secure_delete=ON; DELETE FROM messages WHERE received_day <= date('now','-28 days'); VACUUM;"
