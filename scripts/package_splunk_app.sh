#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
APP_NAME="f1_driver_telemetry"
APP_DIR="$ROOT/splunk/$APP_NAME"
DIST_DIR="$ROOT/dist"
OUTPUT="$DIST_DIR/${APP_NAME}.tar.gz"

[ -f "$APP_DIR/default/app.conf" ] || {
  echo "ERROR: Splunk app not found at $APP_DIR" >&2
  exit 1
}

mkdir -p "$DIST_DIR"
COPYFILE_DISABLE=1 tar \
  --exclude='.DS_Store' \
  --exclude='._*' \
  --exclude='local' \
  -czf "$OUTPUT" \
  -C "$ROOT/splunk" \
  "$APP_NAME"

printf '%s\n' "$OUTPUT"
