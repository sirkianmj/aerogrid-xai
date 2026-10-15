#!/usr/bin/env bash
# run_load_test.sh -- headless Locust wrapper.
# Saves raw CSVs to tests/loadtest/results/<timestamp>/ and prints a
# short summary. The P95 gate is applied from a measured baseline in a
# follow-up. See docs/LOAD_TEST_BASELINE.md once recorded.

set -euo pipefail

USERS="${1:-100}"
RATE="${2:-10}"
DURATION="${3:-60s}"
HOST="http://127.0.0.1:8000"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
LF="${REPO_ROOT}/tests/loadtest/locustfile.py"
STAMP="$(date +%Y%m%dT%H%M%S)"
OUT="${REPO_ROOT}/tests/loadtest/results/${STAMP}"
mkdir -p "${OUT}"

if ! command -v locust >/dev/null 2>&1; then
    echo "error: locust not found on PATH" >&2
    echo "hint: conda env update -f environment.yml --prune" >&2
    exit 1
fi

if [ ! -f /tmp/aerogrid-load-tokens.txt ]; then
    echo "error: /tmp/aerogrid-load-tokens.txt missing" >&2
    echo "hint: scripts/seed_load_tenants.sh 100" >&2
    exit 1
fi

if ! curl -fsS -o /dev/null "${HOST}/health"; then
    echo "error: backend not reachable at ${HOST}" >&2
    exit 1
fi

echo "users=${USERS} rate=${RATE} duration=${DURATION} host=${HOST}"
echo "output=${OUT}"

locust -f "${LF}" \
    --headless \
    -u "${USERS}" \
    -r "${RATE}" \
    -t "${DURATION}" \
    --host "${HOST}" \
    --csv "${OUT}/locust" \
    --only-summary \
    --exit-code-on-error 0

echo
echo "results in ${OUT}"
ls -la "${OUT}"

python3 - "${OUT}" <<'PYSUMMARY'
import csv, sys
from pathlib import Path
out = Path(sys.argv[1])
stats = out / "locust_stats.csv"
if not stats.exists():
    print("no stats CSV produced")
    raise SystemExit(0)
print()
print("request | reqs | fails | p50 | p95 | p99")
print("-" * 70)
rows = list(csv.DictReader(stats.open()))
for row in rows:
    n = row.get("Name", "")
    if not n or n == "Aggregated":
        continue
    print(f"{n} | {row.get('Request Count')} | {row.get('Failure Count')} | "
          f"{row.get('50%')} | {row.get('95%')} | {row.get('99%')}")
for row in rows:
    if row.get("Name") == "Aggregated":
        print()
        print(f"AGGREGATED reqs={row.get('Request Count')} fails={row.get('Failure Count')} "
              f"p50={row.get('50%')} p95={row.get('95%')} p99={row.get('99%')} max={row.get('100%')}")
PYSUMMARY
