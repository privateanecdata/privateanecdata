#!/bin/sh
# Private Anecdata — tell this Mac when a contact message arrives. launchd runs it every 3 hours.
#
# Outgoing email is blocked on DigitalOcean, so the site stores contact messages and the operator
# reads them on the server (pa-messages). This script uses a dedicated key, ~/.ssh/pa_notify_ed25519,
# which the server locks to one command: print "<messages waiting>|<latest received day>". It can
# read nothing else, and it never sees a message.
HOST=root@134.122.18.172
DIR="$HOME/Library/Application Support/PrivateAnecdata"; STATE="$DIR/contact-seen"
mkdir -p "$DIR"
out=$(ssh -i "$HOME/.ssh/pa_notify_ed25519" -o BatchMode=yes -o IdentitiesOnly=yes -o ConnectTimeout=20 "$HOST" 2>/dev/null) || exit 0
count=${out%%|*}; day=${out#*|}
case "$count" in ''|*[!0-9]*) exit 0 ;; esac
if [ -f "$STATE" ]; then
  last=$(cat "$STATE"); lcount=${last%%|*}; lday=${last#*|}
  if [ "$count" -gt "$lcount" ] || { [ -n "$day" ] && [ "$day" \> "$lday" ]; }; then
    osascript -e "display notification \"New contact message ($count waiting). Read them with: pa-messages\" with title \"Private Anecdata\" sound name \"default\""
  fi
fi
printf '%s\n' "$out" > "$STATE"
