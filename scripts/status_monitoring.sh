#!/usr/bin/env bash
# status_monitoring.sh — one-glance health of the monitoring stack.

set -uo pipefail

echo "=== brew services ==="
brew services list 2>/dev/null | grep -E "prometheus|grafana" || echo "  (neither installed)"

echo
echo "=== endpoints ==="
if curl -fsS -o /dev/null http://localhost:9090/-/healthy 2>/dev/null; then
    echo "  prometheus   http://localhost:9090  OK"
else
    echo "  prometheus   http://localhost:9090  DOWN"
fi
if curl -fsS -o /dev/null http://localhost:3000/api/health 2>/dev/null; then
    echo "  grafana      http://localhost:3000  OK"
else
    echo "  grafana      http://localhost:3000  DOWN"
fi
if curl -fsS -o /dev/null http://127.0.0.1:8000/metrics 2>/dev/null; then
    echo "  backend      http://127.0.0.1:8000/metrics  OK"
else
    echo "  backend      http://127.0.0.1:8000/metrics  DOWN"
fi

echo
echo "=== prometheus targets ==="
curl -sS http://localhost:9090/api/v1/targets 2>/dev/null \
  | python3 -c "import json,sys; d=json.load(sys.stdin); [print(f'  {t[\"labels\"][\"job\"]:20s} {t[\"health\"]:8s} {t[\"scrapeUrl\"]}') for t in d[\"data\"][\"activeTargets\"]]" \
  2>/dev/null || echo "  (prometheus not reachable)"
