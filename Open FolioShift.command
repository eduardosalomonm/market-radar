#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
if curl --silent --fail --max-time 2 http://127.0.0.1:8502/_stcore/health >/dev/null; then
  open http://127.0.0.1:8502/
else
  echo "Starting your private app. Keep this window open."
  echo "Open http://127.0.0.1:8502/ once the app is ready."
  exec ./start.sh
fi
