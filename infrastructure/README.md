# Production deployment (Sprint 11 s11-1)

Native macOS deployment of the AeroGrid stack via launchd. No Docker,
no Kubernetes, no cloud VMs — the constraint from D2 of the roadmap.

## What runs

| Service | Label | Port(s) | Plist |
|---|---|---|---|
| PostgreSQL 16 | `com.forgex4.aerogrid.postgres` | 5432 | `launchd/com.forgex4.aerogrid.postgres.plist` |
| Redis 8 | `com.forgex4.aerogrid.redis` | 6379 | `launchd/com.forgex4.aerogrid.redis.plist` |
| MinIO (S3) | `com.forgex4.aerogrid.minio` | 9000, 9001 | `launchd/com.forgex4.aerogrid.minio.plist` |
| FastAPI backend | `com.forgex4.aerogrid.backend` | 8000 | `launchd/com.forgex4.aerogrid.backend.plist` |
| Vite preview | `com.forgex4.aerogrid.frontend` | 5173 | `launchd/com.forgex4.aerogrid.frontend.plist` |

Each plist is a **template**. The committed files carry three
placeholders:

- `__REPO_ROOT__` — absolute path to this repository
- `__CONDA_ENV__` — absolute path to the `aerogrid` conda environment
- `__LOG_DIR__` — `~/Library/Logs/aerogrid` (created on install)

`install.sh` substitutes them at install time. The committed files never
contain a user-specific path.

## Install

    conda activate aerogrid
    infrastructure/scripts/install.sh

The script:

1. Verifies the repo and the conda env exist.
2. Runs `npm run build` in `frontend/` **once** if `frontend/dist/` is
   missing. The build is a deployment step, not a restart step.
3. Substitutes placeholders and writes the five plists to
   `~/Library/LaunchAgents/`.
4. Loads each plist under the current GUI session with
   `launchctl bootstrap gui/$UID`.

Idempotent: running `install.sh` twice replaces the plists and reloads
the services.

## Status

    infrastructure/scripts/status.sh

Prints every `launchctl list` entry matching `aerogrid` and the state of
each listening port.

## Uninstall

    infrastructure/scripts/uninstall.sh

Boots out every `com.forgex4.aerogrid.*` agent and removes its plist.
Logs under `~/Library/Logs/aerogrid/` are preserved.

## Logs

Each plist writes stdout and stderr to `~/Library/Logs/aerogrid/`:

    postgres.out.log    postgres.err.log
    redis.out.log       redis.err.log
    minio.out.log       minio.err.log
    backend.out.log     backend.err.log
    frontend.out.log    frontend.err.log

These are the primary diagnostic source when a service fails to start
under launchd (the failure does not surface anywhere else).

## Why launchd and not `scripts/start_services.sh`

`start_services.sh` is the developer path: it starts the services for
the duration of a working session. launchd is the deployment path: it
starts them at login, restarts them on failure, and keeps them alive
across shell sessions.

Both paths use the same data directories (`data/postgresql`,
`data/redis`, `data/minio`) and the same conda env, so switching between
them is safe as long as only one is active at a time. If you have run
`start_services.sh`, stop those services first — the two will otherwise
compete for the same ports.

## Why the frontend uses a wrapper script

`npm run preview` is not itself a launchd-friendly program: npm spawns
Vite as a child and the launchd plist would otherwise track npm, not the
server. `run_frontend.sh` uses `exec` so the shell is replaced by npm;
when Vite exits, npm exits, and launchd sees the true exit.

## What this does NOT do

- Does not run the frontend build on every start (deliberate — see
  above). After a frontend code change, run `npm run build` in
  `frontend/` and the next restart of the frontend service serves the
  new bundle.
- Does not provision or migrate the database. Run
  `scripts/start_services.sh` and apply the migrations before the first
  launchd install, or run the migration loop manually afterwards.
- Does not rotate logs. `~/Library/Logs/aerogrid/*.log` grows
  unbounded; a `newsyslog.d` config is a follow-up.
