# Incident Response

**Scope:** AeroGrid-XAI, deployed natively on macOS via launchd. No
containers, no cloud, single operator.

## Severities

| Severity | Definition | MTTR target |
|---|---|---|
| **P1** | Whole platform down: `/health` non-200, Postgres unreachable, or the frontend does not serve. | 1 hour |
| **P2** | One dependency down but the platform mostly works: Prometheus, Grafana, Redis, or MinIO unreachable while the backend and Postgres are healthy. | 4 hours |
| **P3** | Degraded performance or a non-critical feature is broken. | Next business day |

The MTTR clock starts when the operator learns of the incident.

## Detection

The status page at `/status` reports every dependency with a live
check. Historical data is on the Grafana dashboard.

## Per-component playbooks

### Backend (com.forgex4.aerogrid.backend)

    launchctl list | grep aerogrid.backend
    tail -50 ~/Library/Logs/aerogrid/backend.err.log
    launchctl kickstart -k gui/$UID/com.forgex4.aerogrid.backend

The second command shows the Python traceback if the service crashed
on start. The third restarts the service cleanly.

### PostgreSQL (com.forgex4.aerogrid.postgres)

Symptoms: /status reports postgres down. Almost everything else fails.

    launchctl list | grep aerogrid.postgres
    tail -50 data/postgresql/server.log
    launchctl kickstart -k gui/$UID/com.forgex4.aerogrid.postgres
    psql -U aerogrid -p 5432 -d aerogrid -c "SELECT 1"

A stale data/postgresql/postmaster.pid from a hard kill will block
startup; removing it is safe.

### Redis (com.forgex4.aerogrid.redis)

Symptoms: rate limiting fails closed on /auth/*, so sign-in and signup
return 503. Reads continue to work.

    launchctl list | grep aerogrid.redis
    tail -50 data/redis/server.log
    launchctl kickstart -k gui/$UID/com.forgex4.aerogrid.redis
    redis-cli -p 6379 ping

### MinIO (com.forgex4.aerogrid.minio)

Symptoms: exports fail. Scientific endpoints do not depend on MinIO.

    launchctl list | grep aerogrid.minio
    tail -50 data/minio/server.log
    launchctl kickstart -k gui/$UID/com.forgex4.aerogrid.minio
    curl -sS http://127.0.0.1:9000/minio/health/live

### Prometheus and Grafana (Homebrew services)

Symptoms: dashboards stale or unreachable. No scientific function is
affected.

    brew services list | grep -E "prometheus|grafana"
    tail -50 /opt/homebrew/var/log/prometheus.log
    tail -50 /opt/homebrew/var/log/grafana/grafana.log
    brew services restart prometheus
    brew services restart grafana

### Frontend (com.forgex4.aerogrid.frontend)

    launchctl list | grep aerogrid.frontend
    tail -50 ~/Library/Logs/aerogrid/frontend.err.log
    cd frontend && npm run build
    launchctl kickstart -k gui/$UID/com.forgex4.aerogrid.frontend

The build step is required if the frontend source changed; launchd
serves the bundle from frontend/dist/.

## Multi-dependency incidents

If more than one launchd service is down, the cause is likely a system
event rather than a component failure.

    launchctl list | grep aerogrid
    uptime
    log show --last 30m --predicate 'process == "launchd"' --style compact | tail -20

`Service only ran for ... seconds` means the service is
crash-looping. `Failed to spawn` means a config error in the plist.

## Communication

For P1 and P2, append a short timeline to
~/Library/Logs/aerogrid/incidents.log.

The status page at /status is the operator's own view. It is not
exposed publicly in this deployment. A future public deployment should
expose /status read-only and unauthenticated so users see outages as
they happen.

## Post-incident

Within 48 hours of a P1 or P2 closure, write a short post-mortem:
what happened, impact, root cause, and what changed to prevent
recurrence. Post-mortems live in docs/postmortems/.

## Escalation

Single-operator deployment. No on-call rotation. If the operator is
unavailable, the platform is unavailable. This is an explicit
consequence of the D2 deployment model; a paid on-call service would
violate D2 and is out of scope.
