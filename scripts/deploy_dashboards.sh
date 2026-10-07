#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
APP_NAME="f1_driver_telemetry"
VIEWS_DIR="$ROOT/splunk/$APP_NAME/default/data/ui/views"
SPLUNK_ENV="${SPLUNK_ENV:-$HOME/.splunk-podman/.env}"
BASE="https://127.0.0.1:8089/servicesNS/admin/$APP_NAME/data/ui/views"

[ -f "$SPLUNK_ENV" ] || {
  echo "ERROR: Splunk runtime file not found: $SPLUNK_ENV" >&2
  exit 1
}

set -a
# shellcheck disable=SC1090
. "$SPLUNK_ENV"
set +a

AUTH_FILE="$(mktemp)"
RESPONSE_FILE="$(mktemp)"
trap 'rm -f "$AUTH_FILE" "$RESPONSE_FILE"' EXIT
umask 077
cat >"$AUTH_FILE" <<EOF
machine 127.0.0.1
login admin
password $SPLUNK_PASSWORD
EOF

for view in "$VIEWS_DIR"/*.xml; do
  name="$(basename "$view" .xml)"
  code="$(curl -sk --netrc-file "$AUTH_FILE" -o "$RESPONSE_FILE" -w '%{http_code}' \
    -X POST "$BASE/$name" \
    --data-urlencode "eai:data@$view" \
    --data-urlencode 'output_mode=json')"
  if [ "$code" = "404" ]; then
    code="$(curl -sk --netrc-file "$AUTH_FILE" -o "$RESPONSE_FILE" -w '%{http_code}' \
      -X POST "$BASE" \
      --data-urlencode "name=$name" \
      --data-urlencode "eai:data@$view" \
      --data-urlencode 'output_mode=json')"
  fi
  case "$code" in
    2??) printf 'registered %s\n' "$name" ;;
    *)
      printf 'ERROR: Splunk rejected %s (HTTP %s):\n' "$name" "$code" >&2
      python3 -c \
        'import json,sys; data=json.load(open(sys.argv[1])); print(data.get("messages", data))' \
        "$RESPONSE_FILE" >&2 || true
      exit 1
      ;;
  esac
done
