#!/usr/bin/env bash
set -euo pipefail

SPLUNK_ENV="${SPLUNK_ENV:-$HOME/.splunk-podman/.env}"
SPLUNK_MGMT_URL="${SPLUNK_MGMT_URL:-https://127.0.0.1:8089}"

[ "$#" -eq 1 ] || {
  echo "Usage: $0 '<SPL search without the leading search command>'" >&2
  exit 2
}
[ -f "$SPLUNK_ENV" ] || {
  echo "ERROR: Splunk runtime file not found: $SPLUNK_ENV" >&2
  exit 1
}

set -a
# shellcheck disable=SC1090
. "$SPLUNK_ENV"
set +a

[ -n "${SPLUNK_PASSWORD:-}" ] || {
  echo "ERROR: SPLUNK_PASSWORD is missing from $SPLUNK_ENV" >&2
  exit 1
}

AUTH_FILE="$(mktemp)"
trap 'rm -f "$AUTH_FILE"' EXIT
umask 077
cat >"$AUTH_FILE" <<EOF
machine 127.0.0.1
login admin
password $SPLUNK_PASSWORD
EOF

curl -skf --netrc-file "$AUTH_FILE" \
  "$SPLUNK_MGMT_URL/services/search/jobs/export" \
  --data-urlencode "search=search $1" \
  --data-urlencode 'output_mode=json' \
  --data-urlencode 'count=0'
