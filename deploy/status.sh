#!/usr/bin/env sh
# Operator status over SSH: counts and health, never rows. Run as the service user or root.
#   sh /srv/private-anecdata/repo/deploy/status.sh
set -eu
DB="${PA_DB_PATH:-/srv/private-anecdata/data/reports.db}"
CDB="${PA_CONTACT_DB_PATH:-/srv/private-anecdata/data/contact.db}"
echo "== service";   systemctl is-active private-anecdata caddy tor 2>/dev/null | paste -sd' ' - || true
echo "== disk";      df -h /srv/private-anecdata 2>/dev/null | tail -1
if [ -f "$DB" ]; then
  echo "== reports";  sqlite3 "$DB" "SELECT COUNT(*) || ' committed, ' || (SELECT COUNT(*) FROM exclusions) || ' excluded' FROM reports"
  echo "== by class (top compounds hidden below 10, as the site would show them)"
  sqlite3 "$DB" "SELECT compound, COUNT(*) FROM reports GROUP BY compound HAVING COUNT(*) >= 10 ORDER BY 2 DESC LIMIT 15"
  echo "== last 7 days"; sqlite3 "$DB" "SELECT received_day, COUNT(*) FROM reports WHERE received_day >= date('now','-7 days') GROUP BY 1 ORDER BY 1"
else echo "== no store yet"; fi
if [ -f "$CDB" ]; then echo "== contact messages waiting: $(sqlite3 "$CDB" 'SELECT COUNT(*) FROM messages')"; fi
