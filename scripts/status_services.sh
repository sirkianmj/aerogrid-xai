#!/usr/bin/env bash
set -u

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
DATA_DIR="${REPO_ROOT}/data"
PG_DATA="${DATA_DIR}/postgresql"
PG_PORT="5432"
REDIS_PORT="6379"
MINIO_PORT="9000"

if [ ! -f "${PG_DATA}/PG_VERSION" ]; then
    echo "PostgreSQL: NOT INITIALIZED"
elif pg_ctl -D "${PG_DATA}" status > /dev/null 2>&1; then
    echo "PostgreSQL: RUNNING on port ${PG_PORT}"
else
    echo "PostgreSQL: STOPPED"
fi

if redis-cli -p "${REDIS_PORT}" ping > /dev/null 2>&1; then
    echo "Redis: RUNNING on port ${REDIS_PORT}"
else
    echo "Redis: STOPPED"
fi

if curl -sf "http://127.0.0.1:${MINIO_PORT}/minio/health/live" > /dev/null 2>&1; then
    echo "MinIO: RUNNING on port ${MINIO_PORT}"
else
    echo "MinIO: STOPPED"
fi
