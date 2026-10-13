#!/usr/bin/env bash
set -u

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
DATA_DIR="${REPO_ROOT}/data"
PG_DATA="${DATA_DIR}/postgresql"
PG_PORT="5432"
REDIS_PORT="6379"
MINIO_PORT="9000"

if pg_ctl -D "${PG_DATA}" status > /dev/null 2>&1; then
    pg_ctl -D "${PG_DATA}" stop -m fast
    echo "PostgreSQL stopped."
else
    echo "PostgreSQL not running."
fi

if redis-cli -p "${REDIS_PORT}" ping > /dev/null 2>&1; then
    redis-cli -p "${REDIS_PORT}" shutdown nosave
    echo "Redis stopped."
else
    echo "Redis not running."
fi

# MinIO does not ship with a shutdown command. Its process is killed by
# PID lookup. The health endpoint is used to confirm the process has
# actually exited before reporting success.
MINIO_PIDS=$(pgrep -f "minio server ${DATA_DIR}/minio" || true)
if [ -n "${MINIO_PIDS}" ]; then
    kill ${MINIO_PIDS}
    sleep 1
    if curl -sf "http://127.0.0.1:${MINIO_PORT}/minio/health/live" > /dev/null 2>&1; then
        echo "MinIO still responding after kill; check manually."
    else
        echo "MinIO stopped."
    fi
else
    echo "MinIO not running."
fi
