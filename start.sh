#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$PROJECT_DIR"

PYTHON_BIN="${PYTHON:-python3}"
if ! "$PYTHON_BIN" -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 9) else 1)'; then
  echo "FolioShift requires Python 3.9 or newer. Set PYTHON=/absolute/path/to/python3."
  exit 1
fi

if [ ! -x .venv/bin/python ]; then
  "$PYTHON_BIN" -m venv .venv
fi

.venv/bin/python -m pip install --disable-pip-version-check --no-build-isolation -e .
mkdir -p data
if [ ! -f .env ]; then
  cp .env.example .env
fi

RADAR_PORT="$(sed -n 's/^MARKET_RADAR_PORT=//p' .env | tail -n 1 | tr -d '[:space:]')"
if [ -z "$RADAR_PORT" ]; then
  RADAR_PORT="8502"
fi

SCHEDULER_PID=""
cleanup() {
  if [ -n "$SCHEDULER_PID" ]; then
    kill "$SCHEDULER_PID" 2>/dev/null || true
    wait "$SCHEDULER_PID" 2>/dev/null || true
  fi
}
trap cleanup EXIT INT TERM

if grep -Eq '^ALPACA_API_KEY_ID=.+$' .env && grep -Eq '^ALPACA_API_SECRET_KEY=.+$' .env; then
  .venv/bin/market-radar scheduler >> data/scheduler.log 2>&1 &
  SCHEDULER_PID=$!
  echo "After-close scheduler started. Log: data/scheduler.log"
else
  echo "Live scheduler is disabled until Alpaca credentials are added to .env."
fi

.venv/bin/market-radar bootstrap
echo ""
echo "FolioShift is starting at http://127.0.0.1:${RADAR_PORT}"
echo "Keep this terminal window open while presenting the dashboard."
echo ""
.venv/bin/market-radar serve --port "$RADAR_PORT"
