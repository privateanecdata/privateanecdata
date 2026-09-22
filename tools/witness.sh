#!/usr/bin/env sh
# Sign a release and witness it in two independent public logs.
#
#   tools/witness.sh keygen                       # once: creates the release signing key
#   tools/witness.sh sign    releases/2026-12     # detached signature on release.json
#   tools/witness.sh rekor   releases/2026-12     # Sigstore Rekor (public-good instance, v1 API)
#   tools/witness.sh ots     releases/2026-12     # OpenTimestamps (Bitcoin-anchored)
#   tools/witness.sh upgrade releases/2026-12     # after ~a day: upgrade the .ots proof (mandatory)
#   tools/witness.sh all     releases/2026-12     # sign + rekor + ots
#   tools/witness.sh all     spec/RELEASE_SPEC.md # any single file: the spec freeze, a policy version
#
# DRY_RUN=1 prints the commands instead of running them. Test on a throwaway release first:
# Rekor entries are permanent, public, and cannot be removed. Only hashes ever go in.
#
# The signed artifact is release.json, which already carries the SHA-256 of every other file in
# the release, the Merkle root, and the hash of the release specification. Nothing in release.json
# is modified after signing; the signature, Rekor entry and .ots proof are written beside it in
# witness/. release.json contains no row, no partial row, and no count below the cell floor
# (tools/release.py audits that before writing it).
#
# Requires: openssl; rekor-cli (https://github.com/sigstore/rekor); ots (pip install opentimestamps-client).
set -eu

KEY_DIR="${PA_KEY_DIR:-$HOME/.config/private-anecdata}"
KEY="$KEY_DIR/release-signing-key.pem"
PUB="$KEY_DIR/release-signing-key.pub.pem"
run() { if [ "${DRY_RUN:-0}" = 1 ]; then echo "+ $*"; else "$@"; fi; }

cmd="${1:-}"; rel="${2:-}"
case "$cmd" in
  keygen)
    [ -e "$KEY" ] && { echo "key exists: $KEY"; exit 1; }
    mkdir -p "$KEY_DIR"; chmod 700 "$KEY_DIR"
    run openssl ecparam -genkey -name prime256v1 -noout -out "$KEY"
    run chmod 600 "$KEY"
    run openssl ec -in "$KEY" -pubout -out "$PUB"
    echo "signing key: $KEY"; echo "public key:  $PUB  (publish this; copy to releases/pubkey.pem)"
    ;;
  sign|rekor|ots|upgrade|all)
    if [ -n "$rel" ] && [ -f "$rel/release.json" ]; then
      W="$rel/witness"; RJ="$rel/release.json"; NAME="release.json"
    elif [ -n "$rel" ] && [ -f "$rel" ]; then
      # A single file: artifacts go in witness/ beside it, named after the file.
      W="$(dirname "$rel")/witness"; RJ="$rel"; NAME="$(basename "$rel")"
    else
      echo "usage: $0 $cmd releases/<id> | path/to/file"; exit 1
    fi
    mkdir -p "$W"
    HASH=$(openssl dgst -sha256 "$RJ" | sed 's/^.*= //')
    ;;
  *)
    sed -n '2,20p' "$0"; exit 1 ;;
esac

do_sign() {
  [ -f "$KEY" ] || { echo "no signing key; run: $0 keygen"; exit 1; }
  run openssl dgst -sha256 -sign "$KEY" -out "$W/$NAME.sig" "$RJ"
  run cp "$PUB" "$W/pubkey.pem"
  run openssl dgst -sha256 -verify "$W/pubkey.pem" -signature "$W/$NAME.sig" "$RJ"
  echo "signed: $W/$NAME.sig  ($NAME sha256 $HASH)"
}

do_rekor() {
  [ -f "$W/$NAME.sig" ] || { echo "sign first"; exit 1; }
  # hashedrekord: the log stores only the artifact hash, the signature, and the public key.
  if [ "${DRY_RUN:-0}" = 1 ]; then
    echo "+ rekor-cli upload --type hashedrekord:0.0.1 --artifact-hash $HASH --signature $W/$NAME.sig --pki-format x509 --public-key $W/pubkey.pem"
    return
  fi
  command -v rekor-cli >/dev/null || { echo "rekor-cli not installed"; exit 1; }
  out=$(rekor-cli upload --type hashedrekord:0.0.1 --artifact-hash "$HASH" \
        --signature "$W/$NAME.sig" --pki-format x509 --public-key "$W/pubkey.pem")
  echo "$out"
  idx=$(echo "$out" | sed -n 's/.*index \([0-9]*\).*/\1/p' | head -1)
  uuid=$(echo "$out" | sed -n 's#.*/entries/\([0-9a-f]*\).*#\1#p' | head -1)
  printf '{\n "artifact": "%s",\n "artifact_sha256": "%s",\n "log": "rekor.sigstore.dev",\n "log_index": %s,\n "uuid": "%s",\n "type": "hashedrekord:0.0.1"\n}\n' \
    "$NAME" "$HASH" "${idx:-null}" "$uuid" > "$W/$NAME.rekor.json"
  echo "recorded: $W/$NAME.rekor.json"
}

do_ots() {
  command -v ots >/dev/null || { echo "ots client not installed (pip install opentimestamps-client)"; exit 1; }
  run ots stamp "$RJ"
  run mv "$RJ.ots" "$W/$NAME.ots"
  echo "stamped: $W/release.json.ots — run '$0 upgrade $rel' after a day so the proof no longer depends on a calendar server"
}

do_upgrade() {
  run ots upgrade "$W/$NAME.ots"
  run ots verify -f "$RJ" "$W/$NAME.ots"
}

case "$cmd" in
  sign) do_sign ;;
  rekor) do_rekor ;;
  ots) do_ots ;;
  upgrade) do_upgrade ;;
  all) do_sign; do_rekor; do_ots ;;
esac
