#!/usr/bin/env bash
# run_frontend.sh — Vite preview served under launchd.
#
# launchd invokes this in the foreground; it does not source shell
# profiles, so PATH is set explicitly here. The build is a deployment
# step performed by install.sh; rebuilding on every restart would slow
# service recovery and add no value.

set -euo pipefail

REPO_ROOT="${1:?repo root required}"
CONDA_ENV="${2:?conda env path required}"

cd "${REPO_ROOT}/frontend"
export PATH="${CONDA_ENV}/bin:/usr/bin:/bin:/usr/sbin:/sbin"

exec npm run preview -- --host 127.0.0.1 --port 5173
