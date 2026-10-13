#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
DATA_DIR="${REPO_ROOT}/data"
PG_DATA="${DATA_DIR}/postgresql"
PG_USER="aerogrid"
PG_DB="aerogrid"
PG_PORT="5432"
REDIS_DATA="${DATA_DIR}/redis"
REDIS_PORT="6379"
MINIO_DATA="${DATA_DIR}/minio"
MINIO_PORT="9000"
MINIO_CONSOLE_PORT="9001"
MINIO_ROOT_USER="aerogrid"
MINIO_ROOT_PASSWORD="aerogrid-dev"

mkdir -p "${PG_DATA}" "${REDIS_DATA}" "${MINIO_DATA}"

# --- PostgreSQL -----------------------------------------------------------
# The PostgreSQL superuser created by initdb is named "aerogrid", not the
# OS user. Every subsequent psql / createdb / createuser call must pass
# -U aerogrid to connect as that role. Passing -h 127.0.0.1 as the OS
# user would try to authenticate as the OS username and fail because no
# such role exists; the local Unix-socket connection is used instead.
if [ ! -f "${PG_DATA}/PG_VERSION" ]; then
    echo "Initializing PostgreSQL data directory at ${PG_DATA}"
    initdb -D "${PG_DATA}" --encoding=UTF8 --locale=C --username="${PG_USER}"
    pg_ctl -D "${PG_DATA}" -l "${PG_DATA}/server.log" -o "-p ${PG_PORT}" start
    sleep 2
    createdb -U "${PG_USER}" -p "${PG_PORT}" -O "${PG_USER}" "${PG_DB}"
    echo "PostgreSQL initialized and started on port ${PG_PORT}."
else
    if pg_ctl -D "${PG_DATA}" status > /dev/null 2>&1; then
        echo "PostgreSQL already running."
    else
        pg_ctl -D "${PG_DATA}" -l "${PG_DATA}/server.log" -o "-p ${PG_PORT}" start
        echo "PostgreSQL started on port ${PG_PORT}."
    fi
fi

# --- Redis ----------------------------------------------------------------
if redis-cli -p "${REDIS_PORT}" ping > /dev/null 2>&1; then
    echo "Redis already running."
else
    redis-server --dir "${REDIS_DATA}" --port "${REDIS_PORT}" --daemonize yes \
        --logfile "${REDIS_DATA}/server.log"
    echo "Redis started on port ${REDIS_PORT}."
fi

# --- MinIO ----------------------------------------------------------------
# MinIO reads MINIO_ROOT_USER and MINIO_ROOT_PASSWORD from the environment
# on first start. Changing them later requires re-initializing the data
# directory. The values below are development credentials; a production
# deployment sets real values via the environment and does not commit them.
if curl -sf "http://127.0.0.1:${MINIO_PORT}/minio/health/live" > /dev/null 2>&1; then
    echo "MinIO already running."
else
    MINIO_ROOT_USER="${MINIO_ROOT_USER}" \
    MINIO_ROOT_PASSWORD="${MINIO_ROOT_PASSWORD}" \
    nohup minio server "${MINIO_DATA}" \
        --address "127.0.0.1:${MINIO_PORT}" \
        --console-address "127.0.0.1:${MINIO_CONSOLE_PORT}" \
        > "${MINIO_DATA}/server.log" 2>&1 &
    echo "MinIO starting on port ${MINIO_PORT} (console ${MINIO_CONSOLE_PORT})."
    sleep 2
fi

echo "Services started."
