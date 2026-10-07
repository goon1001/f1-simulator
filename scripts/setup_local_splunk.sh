#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
APP_NAME="f1_driver_telemetry"
APP_SRC="$ROOT/splunk/$APP_NAME"
APPS_DIR="${SPLUNK_APPS_DIR:-$HOME/splunk-apps}"
SPLUNK_ENV="${SPLUNK_ENV:-$HOME/.splunk-podman/.env}"
RUNTIME_DIR="${F1_RUNTIME_DIR:-$HOME/.f1-simulator}"
F1_ENV="$RUNTIME_DIR/local.env"
SPLUNK_CONTAINER="${SPLUNK_CONTAINER:-splunk-dev}"
COLLECTOR_URL="${COLLECTOR_URL:-http://127.0.0.1:8501}"
HEC_NAME="f1-telemetry"
HEC_INDEX="data_drivers_f1_2025"

log() {
  printf '==> %s\n' "$*"
}

die() {
  printf 'ERROR: %s\n' "$*" >&2
  exit 1
}

for tool in podman curl python3 tar uuidgen; do
  command -v "$tool" >/dev/null 2>&1 || die "$tool is required."
done

[ -f "$SPLUNK_ENV" ] || die "Splunk runtime file not found: $SPLUNK_ENV"
[ -f "$APP_SRC/default/app.conf" ] || die "Splunk app not found: $APP_SRC"

set -a
# shellcheck disable=SC1090
. "$SPLUNK_ENV"
set +a

[ -n "${SPLUNK_PASSWORD:-}" ] || die "SPLUNK_PASSWORD is missing from $SPLUNK_ENV"

umask 077
mkdir -p "$RUNTIME_DIR"
if [ -f "$F1_ENV" ]; then
  # shellcheck disable=SC1090
  . "$F1_ENV"
else
  F1_HEC_TOKEN="$(uuidgen | tr '[:upper:]' '[:lower:]')"
  printf 'F1_HEC_TOKEN=%s\n' "$F1_HEC_TOKEN" >"$F1_ENV"
fi
[ -n "${F1_HEC_TOKEN:-}" ] || die "F1_HEC_TOKEN is missing from $F1_ENV"

AUTH_FILE="$(mktemp)"
HEC_CURL_FILE="$(mktemp)"
cleanup() {
  rm -f "$AUTH_FILE" "$HEC_CURL_FILE"
}
trap cleanup EXIT

cat >"$AUTH_FILE" <<EOF
machine 127.0.0.1
login admin
password $SPLUNK_PASSWORD
EOF
cat >"$HEC_CURL_FILE" <<EOF
header = "Authorization: Splunk $F1_HEC_TOKEN"
insecure
silent
show-error
fail
EOF
chmod 600 "$AUTH_FILE" "$HEC_CURL_FILE" "$F1_ENV"

"$ROOT/podman/f1ctl" preflight >/dev/null

log "Staging $APP_NAME in $APPS_DIR..."
mkdir -p "$APPS_DIR"
rm -rf "$APPS_DIR/$APP_NAME"
mkdir -p "$APPS_DIR/$APP_NAME"
COPYFILE_DISABLE=1 tar --exclude='.DS_Store' --exclude='._*' -cf - -C "$APP_SRC" . |
  tar -xf - -C "$APPS_DIR/$APP_NAME"
chmod -R a+rX "$APPS_DIR/$APP_NAME"

log "Restarting existing Splunk container to register the app and index..."
podman machine ssh -- podman restart "$SPLUNK_CONTAINER" >/dev/null

log "Waiting for Splunk management API..."
ready=false
for _ in $(seq 1 90); do
  code="$(curl -sk --max-time 3 -o /dev/null -w '%{http_code}' \
    'https://127.0.0.1:8089/services/server/info' || true)"
  if [ "$code" = "200" ] || [ "$code" = "401" ]; then
    ready=true
    break
  fi
  sleep 2
done
[ "$ready" = true ] || die "Splunk management API did not become ready."

REST_BASE='https://127.0.0.1:8089/servicesNS/nobody/splunk_httpinput/data/inputs/http'
if curl -skf --netrc-file "$AUTH_FILE" \
  "$REST_BASE/$HEC_NAME?output_mode=json" >/dev/null 2>&1; then
  log "Updating dedicated F1 HEC input..."
  curl -skf --netrc-file "$AUTH_FILE" -X POST "$REST_BASE/$HEC_NAME" \
    --data-urlencode "token=$F1_HEC_TOKEN" \
    --data-urlencode "index=$HEC_INDEX" \
    --data-urlencode "indexes=$HEC_INDEX" \
    --data-urlencode 'disabled=0' \
    --data-urlencode 'output_mode=json' >/dev/null
else
  log "Creating dedicated F1 HEC input..."
  curl -skf --netrc-file "$AUTH_FILE" -X POST "$REST_BASE" \
    --data-urlencode "name=$HEC_NAME" \
    --data-urlencode "token=$F1_HEC_TOKEN" \
    --data-urlencode "index=$HEC_INDEX" \
    --data-urlencode "indexes=$HEC_INDEX" \
    --data-urlencode 'disabled=0' \
    --data-urlencode 'output_mode=json' >/dev/null
fi

log "Registering Dashboard Studio v2 views through Splunk REST..."
"$ROOT/scripts/deploy_dashboards.sh" >/dev/null

log "Configuring collector HEC destination on the private Podman network..."
printf '{"hec_url":"https://splunk-dev:8088","hec_token":"%s","hec_enabled":true}' \
  "$F1_HEC_TOKEN" |
  curl -fsS -X POST "$COLLECTOR_URL/api/update_hec" \
    -H 'Content-Type: application/json' \
    --data-binary @- >/dev/null

log "Sending an HEC smoke event..."
printf '%s\n' \
  '{"time":'"$(date +%s)"',"host":"rig_setup","source":"f1_2025","sourcetype":"F1SetupTest","event":{"message":"F1 local integration ready","data_mode":"setup"}}' |
  curl --config "$HEC_CURL_FILE" \
    -H 'Content-Type: application/json' \
    --data-binary @- \
    'https://127.0.0.1:8088/services/collector/event' >/dev/null

"$ROOT/scripts/package_splunk_app.sh" >/dev/null
log "Setup complete."
printf 'Collector: %s\n' "$COLLECTOR_URL"
printf 'Splunk app: http://127.0.0.1:8000/app/%s/f1_live_telemetry\n' "$APP_NAME"
printf 'Runtime secrets: %s (mode 600; never commit)\n' "$F1_ENV"
