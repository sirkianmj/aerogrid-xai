#!/usr/bin/env bash
# install_monitoring.sh — install and configure Prometheus + Grafana
# via Homebrew, wire them to the AeroGrid repository's monitoring
# configuration, and start both as Homebrew services (launchd-backed).
#
# Idempotent: running it twice replaces the configs and reloads the
# services.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
MON="${REPO_ROOT}/infrastructure/monitoring"

if [ ! -d "${MON}" ]; then
    echo "error: ${MON} not found" >&2
    exit 1
fi

if ! command -v brew >/dev/null 2>&1; then
    echo "error: Homebrew not found." >&2
    echo "install from https://brew.sh then re-run this script." >&2
    exit 1
fi

BREW_PREFIX="$(brew --prefix)"

echo "=== prometheus ==="
if ! brew list --formula prometheus >/dev/null 2>&1; then
    echo "  installing prometheus..."
    brew install prometheus
else
    echo "  prometheus already installed"
fi

echo "=== grafana ==="
if ! brew list --formula grafana >/dev/null 2>&1; then
    echo "  installing grafana..."
    brew install grafana
else
    echo "  grafana already installed"
fi

echo "=== prometheus config ==="
mkdir -p "${BREW_PREFIX}/etc"
cp "${MON}/prometheus.yml" "${BREW_PREFIX}/etc/prometheus.yml"
echo "  wrote ${BREW_PREFIX}/etc/prometheus.yml"

echo "=== grafana provisioning ==="
# Pin the provisioning path in grafana.ini. Homebrew's Grafana is
# launched with --homepath pointing at the formula share directory,
# where Grafana would otherwise look for conf/provisioning and find
# nothing. The install script writes the provisioning files under
# ${BREW_PREFIX}/etc/grafana/provisioning; the ini must say so.
GRAFANA_INI="${BREW_PREFIX}/etc/grafana/grafana.ini"
if [ ! -f "${GRAFANA_INI}" ]; then
    echo "error: ${GRAFANA_INI} not found; is grafana installed?" >&2
    exit 1
fi

if grep -q "^;provisioning = conf/provisioning" "${GRAFANA_INI}"; then
    sed -i "" "s|^;provisioning = conf/provisioning|provisioning = ${BREW_PREFIX}/etc/grafana/provisioning|" "${GRAFANA_INI}"
    echo "  set paths.provisioning in grafana.ini"
fi
if grep -q "^;permitted_provisioning_paths" "${GRAFANA_INI}"; then
    sed -i "" "s|^;permitted_provisioning_paths = devenv/dev-dashboards\|conf/provisioning|permitted_provisioning_paths = ${BREW_PREFIX}/etc/grafana/provisioning|" "${GRAFANA_INI}"
    echo "  set permitted_provisioning_paths in grafana.ini"
fi

PROV="${BREW_PREFIX}/etc/grafana/provisioning"
if [ -L "${PROV}" ]; then
    rm "${PROV}"
    echo "  removed stale symlink at ${PROV}"
fi
mkdir -p "${PROV}/datasources" "${PROV}/dashboards"

# Remove any stale symlink from a previous install that linked the
# whole provisioning directory. Otherwise the mkdir/cp below would
# operate on paths that resolve into the repository, and cp would
# detect source and destination as the same file and abort the script.
PROV="${BREW_PREFIX}/etc/grafana/provisioning"
if [ -L "${PROV}" ]; then
    rm "${PROV}"
    echo "  removed stale symlink at ${PROV}"
fi
mkdir -p "${PROV}/datasources" "${PROV}/dashboards"

cp "${MON}/grafana/provisioning/datasources/prometheus.yml" \
   "${PROV}/datasources/prometheus.yml"

DASHBOARDS_DIR="${BREW_PREFIX}/var/lib/grafana/dashboards"
if [ -L "${DASHBOARDS_DIR}" ]; then
    rm "${DASHBOARDS_DIR}"
    echo "  removed stale symlink at ${DASHBOARDS_DIR}"
fi
mkdir -p "${DASHBOARDS_DIR}"

sed "s|__DASHBOARDS_DIR__|${DASHBOARDS_DIR}|g" \
    "${MON}/grafana/provisioning/dashboards/default.yml" \
    > "${PROV}/dashboards/default.yml"

cp "${MON}/grafana/dashboards/aerogrid-backend.json" \
   "${DASHBOARDS_DIR}/aerogrid-backend.json"

echo "  wrote ${PROV}/datasources/prometheus.yml"
echo "  wrote ${PROV}/dashboards/default.yml"
echo "  wrote ${DASHBOARDS_DIR}/aerogrid-backend.json"

# Grafana dashboards are copied by the provisioning block above, not
# symlinked. Nothing to do here.

echo "=== start services ==="
brew services restart prometheus >/dev/null
brew services restart grafana >/dev/null
echo "  both restarted"

echo "=== wait for readiness ==="
for i in $(seq 1 20); do
    prom_ok=false
    graf_ok=false
    curl -fsS -o /dev/null http://localhost:9090/-/healthy 2>/dev/null && prom_ok=true
    curl -fsS -o /dev/null http://localhost:3000/api/health 2>/dev/null && graf_ok=true
    if ${prom_ok} && ${graf_ok}; then
        break
    fi
    sleep 1
done

echo
echo "=== status ==="
if curl -fsS -o /dev/null http://localhost:9090/-/healthy; then
    echo "  prometheus: http://localhost:9090  (HTTP 200)"
else
    echo "  prometheus: NOT HEALTHY"
    echo "  logs: ${BREW_PREFIX}/var/log/prometheus.log"
fi
if curl -fsS -o /dev/null http://localhost:3000/api/health; then
    echo "  grafana:    http://localhost:3000  (HTTP 200)"
else
    echo "  grafana:    NOT HEALTHY"
    echo "  logs: ${BREW_PREFIX}/var/log/grafana.log"
fi

echo
echo "grafana login: http://localhost:3000 (admin / admin on first start)"
echo "prometheus UI: http://localhost:9090"
