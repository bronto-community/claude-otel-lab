#!/usr/bin/env bash
# Start the copilot, fire one alert at it, then stop it.
#   scripts/demo.sh [--postmortem] [--chaos]
set -euo pipefail
cd "$(dirname "$0")/.."
PY="${PYTHON:-.venv/bin/python}"
PORT="${PORT:-8000}"
LOG=copilot.log

"$PY" -m uvicorn oncall.app:app --port "$PORT" >"$LOG" 2>&1 &
SERVER=$!
trap 'kill $SERVER 2>/dev/null; wait $SERVER 2>/dev/null || true' EXIT

for _ in $(seq 1 30); do
  curl -sf "http://localhost:$PORT/healthz" >/dev/null && break
  kill -0 $SERVER 2>/dev/null || { cat "$LOG"; exit 1; }
  sleep 0.5
done

COPILOT_URL="http://localhost:$PORT" "$PY" -m oncall.fire_alert "$@"
