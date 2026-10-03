#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
DATA_DIR="${REPO_ROOT}/data"
PG_DATA="${DATA_DIR}/postgresql"
REDIS_DATA="${DATA_DIR}/redis"

mkdir -p "${PG_DATA}" "${REDIS_DATA}"

if [ ! -f "${PG_DATA}/PG_VERSION" ]; then
    echo "Initializing PostgreSQL data directory at ${PG_DATA}"
    initdb -D "${PG_DATA}" --encoding=UTF8 --locale=C --username=aerogrid
    pg_ctl -D "${PG_DATA}" -l "${PG_DATA}/server.log" -o "-p 5432" start
    sleep 2
    createuser -h 127.0.0.1 -p 5432 -s aerogrid || true
    createdb -h 127.0.0.1 -p 5432 -O aerogrid aerogrid || true
    echo "PostgreSQL initialized and started on port 5432."
else
    if pg_ctl -D "${PG_DATA}" status > /dev/null 2>&1; then
        echo "PostgreSQL already running."
    else
        pg_ctl -D "${PG_DATA}" -l "${PG_DATA}/server.log" -o "-p 5432" start
        echo "PostgreSQL started on port 5432."
    fi
fi

if redis-cli -p 6379 ping > /dev/null 2>&1; then
    echo "Redis already running."
else
    redis-server --dir "${REDIS_DATA}" --port 6379 --daemonize yes \
        --logfile "${REDIS_DATA}/server.log"
    echo "Redis started on port 6379."
fi

echo "Services started."
