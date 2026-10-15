#!/usr/bin/env bash
# run_app.sh -- launch AeroGrid-XAI in a browser from the terminal.
#
# Starts one FastAPI process serving both the API and the pre-built
# frontend, then opens the browser. Ctrl-C stops.
#
# Usage:
#   bash scripts/run_app.sh
#   AEROGRID_PORT=9000 bash scripts/run_app.sh

set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO"

PORT="${AEROGRID_PORT:-8000}"

if [ ! -f frontend/dist/index.html ]; then
    echo "==> frontend/dist missing; building"
    ( cd frontend && npm run build )
fi

if lsof -tiTCP:"$PORT" -sTCP:LISTEN >/dev/null 2>&1; then
    echo "==> port $PORT in use; killing previous listener"
    lsof -tiTCP:"$PORT" -sTCP:LISTEN | xargs kill 2>/dev/null || true
    sleep 1
fi

export AEROGRID_PORT="$PORT"
export AEROGRID_DISABLE_RATE_LIMIT=1

# Background-opens the browser once the server answers.
(
    for _ in $(seq 1 60); do
        if curl -fsS -o /dev/null "http://localhost:$PORT/health" 2>/dev/null; then
            open "http://localhost:$PORT/" 2>/dev/null || true
            exit 0
        fi
        sleep 0.5
    done
) &

exec python3 scripts/run_app.py
