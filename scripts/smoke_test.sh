#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SPLUNK_ENV="${SPLUNK_ENV:-$HOME/.splunk-podman/.env}"
APP_NAME="f1_driver_telemetry"
VIEWS=(f1_live_telemetry f1_lap_comparison f1_results_health)

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
SEARCH_FILE="$(mktemp)"
trap 'rm -f "$AUTH_FILE" "$RESPONSE_FILE" "$SEARCH_FILE"' EXIT
umask 077
cat >"$AUTH_FILE" <<EOF
machine 127.0.0.1
login admin
password $SPLUNK_PASSWORD
EOF

curl -fsS --max-time 5 'http://127.0.0.1:8501/healthz' >/dev/null
curl -skf --netrc-file "$AUTH_FILE" \
  "https://127.0.0.1:8089/services/apps/local/$APP_NAME?output_mode=json" >/dev/null

for view in "${VIEWS[@]}"; do
  curl -skf --netrc-file "$AUTH_FILE" \
    "https://127.0.0.1:8089/servicesNS/admin/$APP_NAME/data/ui/views/$view?output_mode=json" \
    -o "$RESPONSE_FILE"
  python3 - "$RESPONSE_FILE" "$view" <<'PY'
import json
import sys

payload = json.load(open(sys.argv[1]))
entry = payload["entry"][0]
content = entry["content"]
assert entry["name"] == sys.argv[2]
assert content.get("isDashboard") is True
assert str(content.get("version")) == "2"
assert len(content.get("eai:data", "")) > 1000
PY
done

"$ROOT/scripts/splunk_search.sh" \
  'index=data_drivers_f1_2025 source=f1_2025 | stats count dc(attempt_id) as attempts' \
  >"$SEARCH_FILE"
python3 - "$SEARCH_FILE" <<'PY'
import json
import sys

rows = [json.loads(line) for line in open(sys.argv[1]) if line.strip()]
results = [row["result"] for row in rows if not row.get("preview") and "result" in row]
assert results, "search returned no final result"
assert int(results[-1]["count"]) > 0, "F1 index is empty"
PY

echo "PASS: collector, Splunk app, three Studio v2 views, and indexed F1 data"
