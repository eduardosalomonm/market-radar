#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
ENV_FILE="$PROJECT_DIR/.env"
RADAR_PORT="8502"
if [ -f "$ENV_FILE" ]; then
  CONFIGURED_PORT="$(sed -n 's/^MARKET_RADAR_PORT=//p' "$ENV_FILE" | tail -n 1 | tr -d '[:space:]')"
  if [ -n "$CONFIGURED_PORT" ]; then
    RADAR_PORT="$CONFIGURED_PORT"
  fi
fi

curl --fail --silent --show-error --max-time 3 "http://127.0.0.1:${RADAR_PORT}/_stcore/health"
echo ""
echo "FolioShift is healthy at http://127.0.0.1:${RADAR_PORT}"
