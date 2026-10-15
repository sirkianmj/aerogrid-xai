# Monitoring (Sprint 11 s11-2)

Native macOS monitoring for AeroGrid-XAI. Prometheus scrapes the
FastAPI backend's `/metrics` endpoint; Grafana reads Prometheus and
renders dashboards. Both run as Homebrew services, managed by launchd
under the hood.

## Why Homebrew and not conda-forge

Neither `prometheus` nor `grafana` exist as conda-forge server binaries
for `osx-arm64`; only their Python client libraries do. Roadmap
decision D2 forbids containers, orchestration platforms, and cloud
VMs — it does not forbid Homebrew for the two services conda-forge
does not publish. The project already uses Homebrew for the GitHub CLI
(`gh`), so this is consistent with existing practice rather than a new
exception.

## Installation

    scripts/install_monitoring.sh

The script:

1. Verifies Homebrew is present.
2. Installs `prometheus` and `grafana` if they are not already
   installed.
3. Copies `prometheus.yml` to `$(brew --prefix)/etc/prometheus.yml`.
4. Symlinks the Grafana provisioning directory into
   `$(brew --prefix)/etc/grafana/provisioning`.
5. Symlinks the dashboards directory into
   `$(brew --prefix)/var/lib/grafana/dashboards`.
6. Starts both services via `brew services`.
7. Verifies each is healthy by probing its HTTP endpoint.

Idempotent: running it twice reinstalls the configs and reloads the
services.

## What runs

| Service | Port | Health URL | Config source |
|---|---|---|---|
| Prometheus | 9090 | http://localhost:9090/-/healthy | `prometheus.yml` |
| Grafana | 3000 | http://localhost:3000/api/health | `grafana/provisioning/` |

## What gets scraped

The single scrape target is `http://127.0.0.1:8000/metrics`, the
FastAPI backend. `prometheus-fastapi-instrumentator` exposes these
metrics out of the box:

- `http_requests_total{handler, method, status}` — counter
- `http_request_duration_seconds{handler}` — histogram
- `http_request_duration_highr_seconds` — high-resolution histogram
- `http_requests_inprogress` — gauge

Custom platform metrics (Z3 solve time, CLEAR-D loop time, delivered
power per UAV, and tenant usage) are added in a follow-up PR.

## Status

    brew services list | grep -E "prometheus|grafana"
    curl -sS http://localhost:9090/-/healthy
    curl -sS http://localhost:3000/api/health

## Logs

    $(brew --prefix)/var/log/prometheus.log
    $(brew --prefix)/var/log/grafana.log

## Uninstall

    brew services stop prometheus grafana
    brew uninstall prometheus grafana

The repository configs under `infrastructure/monitoring/` are not
affected by uninstall; they are the source of truth and can be
reinstalled at any time.
