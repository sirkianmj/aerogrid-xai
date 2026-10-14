#!/usr/bin/env bash
# install.sh — install and load the AeroGrid launchd plists.
#
# Substitutes __REPO_ROOT__, __CONDA_ENV__, and __LOG_DIR__ in each
# plist under infrastructure/launchd/, writes the result to
# ~/Library/LaunchAgents/, and bootstraps each one under the current
# GUI session. Idempotent: running it twice replaces the existing
# agents with the current versions.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
SRC="${REPO_ROOT}/infrastructure/launchd"
DST="${HOME}/Library/LaunchAgents"
LOGS="${HOME}/Library/Logs/aerogrid"

if [ ! -d "${REPO_ROOT}/backend/app" ]; then
    echo "error: ${REPO_ROOT} does not look like the AeroGrid repository" >&2
    exit 1
fi

CONDA_ENV="$(conda info --base 2>/dev/null)/envs/aerogrid"
if [ ! -x "${CONDA_ENV}/bin/uvicorn" ]; then
    echo "error: conda env aerogrid not found at ${CONDA_ENV}" >&2
    echo "hint: run 'conda activate aerogrid' first, or install the env" >&2
    exit 1
fi

mkdir -p "${DST}" "${LOGS}"

if [ ! -d "${REPO_ROOT}/frontend/dist" ]; then
    echo "frontend dist/ missing; building once..."
    (cd "${REPO_ROOT}/frontend" && npm run build)
fi

echo "installing plists to ${DST}"
for src in "${SRC}"/*.plist; do
    name="$(basename "${src}")"
    dst="${DST}/${name}"
    sed \
        -e "s|__REPO_ROOT__|${REPO_ROOT}|g" \
        -e "s|__CONDA_ENV__|${CONDA_ENV}|g" \
        -e "s|__LOG_DIR__|${LOGS}|g" \
        "${src}" > "${dst}"
    chmod 644 "${dst}"
    echo "  wrote ${dst}"
done

echo "loading plists"
for plist in "${DST}"/com.forgex4.aerogrid.*.plist; do
    label="$(basename "${plist}" .plist)"
    launchctl bootout "gui/${UID}/${label}" 2>/dev/null || true
    launchctl bootstrap "gui/${UID}" "${plist}"
    echo "  loaded ${label}"
done

echo
echo "install complete; check status with infrastructure/scripts/status.sh"
