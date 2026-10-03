#!/usr/bin/env bash
set -u

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
DATA_DIR="${REPO_ROOT}/data"
PG_DATA="${DATA_DIR}/postgresql"

if [ ! -f "${PG_DATA}/PG_VERSION" ]; then
    echo "PostgreSQL: NOT INITIALIZED"
elif pg_ctl -D "${PG_DATA}" status > /dev/null 2>&1; then
    echo "PostgreSQL: RUNNING"
else
    echo "PostgreSQL: STOPPED"
fi

if redis-cli -p 6379 ping > /dev/null 2>&1; then
    echo "Redis: RUNNING"
else
    echo "Redis: STOPPED"
fi
