#!/usr/bin/env sh
# Private Anecdata — whole-server setup for a fresh Ubuntu 24.04 host. Run once as root; safe to
# run again after changing an answer (every step checks before it changes anything).
#
#   apt-get install -y git
#   git clone https://github.com/<account>/privateanecdata /srv/private-anecdata/repo
#   sh /srv/private-anecdata/repo/deploy/setup.sh
#
# It asks two questions (hostname, path to the backup public key — defaults to
# deploy/backup.pub, the committed public half of the operator's backup key) and then:
# installs Node, Caddy, Tor and sqlite; creates the service user and directories; builds
# the app with the hostname baked in; installs the systemd unit, Caddyfile, Tor onion service,
# journald limits, cron jobs and firewall; starts everything; prints the
# onion address and what to do next. Every command is visible below — nothing is hidden.
set -eu
[ "$(id -u)" = 0 ] || { echo "run as root (sudo sh deploy/setup.sh)"; exit 1; }
REPO=$(cd "$(dirname "$0")/.." && pwd)
BASE=/srv/private-anecdata
export DEBIAN_FRONTEND=noninteractive

say() { printf '\n== %s\n' "$*"; }
ask() { # ask VAR "question" "default"  — env var wins, then the answer, then the default
  eval "cur=\${$1:-}"
  if [ -z "$cur" ]; then printf '%s [%s]: ' "$2" "$3"; read -r ans; eval "$1=\${ans:-\$3}"; fi
}

ask PA_HOST "Public hostname" "privateanecdata.org"
DEFAULT_PUBKEY=""; [ -f "$REPO/deploy/backup.pub" ] && DEFAULT_PUBKEY="$REPO/deploy/backup.pub"
ask PA_BACKUP_PUBKEY "Path to the backup public key (leave empty to skip backups for now)" "$DEFAULT_PUBKEY"

say "packages"
apt-get update -q
apt-get install -y -q curl ca-certificates gnupg git sqlite3 python3 rsync ufw unattended-upgrades \
  build-essential debian-keyring debian-archive-keyring apt-transport-https
if ! command -v node >/dev/null || [ "$(node -v | cut -c2-3)" -lt 22 ]; then
  curl -fsSL https://deb.nodesource.com/setup_22.x | bash -
  apt-get install -y -q nodejs
fi
if ! command -v caddy >/dev/null; then
  curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/gpg.key' | gpg --dearmor -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg
  curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt' > /etc/apt/sources.list.d/caddy-stable.list
  apt-get update -q && apt-get install -y -q caddy
fi
apt-get install -y -q tor
# No mail program: DigitalOcean blocks outgoing mail (ports 25, 465, 587), so contact messages are
# read on the server (deploy/README.md, "Contact form"). Switch off one left from an earlier setup.
systemctl disable --now postfix >/dev/null 2>&1 || true

say "service user and directories"
id anecdata >/dev/null 2>&1 || useradd -r -s /usr/sbin/nologin -d "$BASE" anecdata
mkdir -p "$BASE/app" "$BASE/data" "$BASE/releases" "$BASE/backups"
chown anecdata:anecdata "$BASE/data" "$BASE/backups"; chmod 700 "$BASE/data" "$BASE/backups"

say "app: build with the hostname baked in (security.allowedDomains)"
# The app reads ../docs and ../spec at build time (the documents and the schema/taxonomy), so they
# sit beside it exactly as in the repository.
rsync -a --delete --exclude node_modules --exclude dist --exclude data "$REPO/app/" "$BASE/app/"
rsync -a --delete "$REPO/docs/" "$BASE/docs/"
rsync -a --delete "$REPO/spec/" "$BASE/spec/"
( cd "$BASE/app" && npm ci --silent && PA_HOST="$PA_HOST" npm run build:prod && npm prune --omit=dev --silent )
rsync -a "$REPO/releases/" "$BASE/releases/"
chown -R root:root "$BASE/app" "$BASE/docs" "$BASE/spec" "$BASE/releases"; chmod -R a+rX "$BASE/app" "$BASE/docs" "$BASE/spec" "$BASE/releases"

say "systemd unit"
install -m 644 "$REPO/deploy/private-anecdata.service" /etc/systemd/system/private-anecdata.service
mkdir -p /etc/systemd/system/private-anecdata.service.d
cat > /etc/systemd/system/private-anecdata.service.d/env.conf <<EOF
[Service]
Environment=PA_CONTACT_TO=
EOF
chmod 600 /etc/systemd/system/private-anecdata.service.d/env.conf

say "journald: process logs in memory only, gone within a day"
mkdir -p /etc/systemd/journald.conf.d
printf '[Journal]\nStorage=volatile\nMaxRetentionSec=1day\n' > /etc/systemd/journald.conf.d/private-anecdata.conf
systemctl restart systemd-journald

say "caddy: TLS, no access log, onion block on 8081"
sed "s/privateanecdata\.org/$PA_HOST/g" "$REPO/deploy/Caddyfile" > /etc/caddy/Caddyfile
caddy validate --config /etc/caddy/Caddyfile >/dev/null

say "tor: onion service -> caddy's 8081 block"
grep -q "HiddenServiceDir /var/lib/tor/anecdata/" /etc/tor/torrc || cat >> /etc/tor/torrc <<'EOF'

HiddenServiceDir /var/lib/tor/anecdata/
HiddenServicePort 80 127.0.0.1:8081
EOF

say "firewall and automatic security updates"
ufw allow OpenSSH >/dev/null; ufw allow 80/tcp >/dev/null; ufw allow 443/tcp >/dev/null
ufw --force enable >/dev/null
systemctl enable --now unattended-upgrades >/dev/null 2>&1 || true

say "cron: encrypted nightly backup, daily contact-message prune"
CRON="0 4 * * * sh $REPO/deploy/prune-contact.sh"
if [ -n "$PA_BACKUP_PUBKEY" ] && [ -f "$PA_BACKUP_PUBKEY" ]; then
  FPR=$(gpg --with-colons --show-keys "$PA_BACKUP_PUBKEY" | awk -F: '/^fpr/{print $10; exit}')
  sudo -u anecdata gpg --batch --import "$PA_BACKUP_PUBKEY" >/dev/null 2>&1 || true
  CRON="$CRON
30 3 * * * PA_BACKUP_KEY=$FPR PA_BACKUP_DIR=$BASE/backups sh $REPO/deploy/backup.sh"
else
  echo "   (no backup key given — backups are NOT scheduled; rerun with the key when you have it)"
fi
printf 'MAILTO=""\n%s\n' "$CRON" | crontab -u anecdata -   # no cron mail: outbound mail is blocked on DigitalOcean

say "start everything"
systemctl daemon-reload
systemctl enable --now private-anecdata caddy tor >/dev/null
systemctl restart private-anecdata caddy tor
sleep 3

say "done"
echo "site:      https://$PA_HOST   (DNS must point here; Caddy fetches the certificate on first request)"
for i in 1 2 3 4 5 6; do [ -f /var/lib/tor/anecdata/hostname ] && break; sleep 5; done
if [ -f /var/lib/tor/anecdata/hostname ]; then echo "tor mirror: http://$(cat /var/lib/tor/anecdata/hostname)"; else echo "tor mirror: address not ready yet — cat /var/lib/tor/anecdata/hostname in a minute"; fi
echo "services:  $(systemctl is-active private-anecdata) app · $(systemctl is-active caddy) caddy · $(systemctl is-active tor) tor"
echo
echo "next: point DNS at this host if you have not; open the site; walk the form once; then clear"
echo "      test rows:  systemctl stop private-anecdata; rm -f $BASE/data/reports.db*; systemctl start private-anecdata"
echo "      status any time:  sh $REPO/deploy/status.sh"
