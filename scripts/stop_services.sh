#!/usr/bin/env bash
set -u

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
DATA_DIR="${REPO_ROOT}/data"
PG_DATA="${DATA_DIR}/postgresql"

if pg_ctl -D "${PG_DATA}" status > /dev/null 2>&1; then
    pg_ctl -D "${PG_DATA}" stop -m fast
    echo "PostgreSQL stopped."
else
    echo "PostgreSQL not running."
fi

if redis-cli -p 6379 ping > /dev/null 2>&1; then
    redis-cli -p 6379 shutdown nosave
    echo "Redis stopped."
else
    echo "Redis not running."
fi
