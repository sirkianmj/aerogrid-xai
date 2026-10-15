# Load Test Baseline

**Author:** Kian Mansouri Jamshidi
**Date:** 2026-10-15
**Sprint:** 11 (task s11-6b)
**Status:** Baseline recorded. Every number below is read from the raw
Locust CSVs under `tests/loadtest/results/`. Nothing in this document is
estimated.

## Purpose

s11-6a merged the load-test instrument (Locust, the tenant seeder, the
runner script) without a pass/fail gate, because the gate must be set
from a measured baseline, not a roadmap guess. This document is that
baseline. It exists so that s11-6c (worker tuning) and s11-7 (scientific
gate under load) have a reference point.

## Method

- **Instrument:** `locust` 2.46.7 from conda-forge, invoked headless by
  `scripts/run_load_test.sh`.
- **Workload:** `tests/loadtest/locustfile.py`. The endpoint mix models
  a browser session, not operator traffic:

  | Weight | Endpoint |
  |-------:|----------|
  | 50%    | `GET  /mission/state?n_uavs=6` |
  | 15%    | `GET  /mission/satellites` |
  | 15%    | `POST /decisions/charge` |
  | 10%    | `GET  /design/presets` |
  | 5%     | `POST /discovery/run` |
  | 5%     | `GET  /saas/whoami` |

  Operator-only routes (`/health`, `/metrics`, `/status`) are excluded
  on purpose: including them would average away the latency that a user
  actually experiences.
- **Client pacing:** `wait_time = between(0.5, 3.0)` seconds per virtual
  user, so each user issues ~0.5 req/s. The measured aggregate request
  rate matches this; the client is the pacing element, not the server.
- **Users:** 4, 8, 16, 32, 64, 128. 2 full sweeps were executed
  and are shown in full below. 1 shorter smoke run(s) were also
  recorded and are listed separately; they are not used in any summary.
- **Duration:** ~60 s per full-sweep level; smoke runs were shorter.
- **Host:** `http://127.0.0.1:8000`, uvicorn 0.32.0 with the default
  single worker, on the local dev machine.
- **Backend state:** started with `AEROGRID_DISABLE_RATE_LIMIT=1` so
  the seeder could issue 100 `/auth/token` calls. Redis running;
  PostgreSQL running; MinIO not running and not exercised by this
  workload.
- **Tokens:** `/tmp/aerogrid-load-tokens.txt`, 100 tokens, one per
  seeded tenant, TTL 24 h.

## Measured baseline

### Smoke runs

Runs too short to be part of a sweep (duration < 45 s). They are recorded here for completeness and excluded from the cross-sweep summary below.

| Users | Requests | Failures | Exceptions | p50 (ms) | p95 (ms) | p99 (ms) | max (ms) | req/s | Run |
|------:|---------:|---------:|-----------:|---------:|---------:|---------:|---------:|------:|-----|
| 10 | 115 | 0 | 0 | 21 | 50 | 140 | 140 | 6.06 | `20261015T164052` |

### Sweep 1

6 runs, users 4 → 128, duration ~60 s per run.

| Users | Requests | Failures | Exceptions | p50 (ms) | p95 (ms) | p99 (ms) | max (ms) | req/s | Run |
|------:|---------:|---------:|-----------:|---------:|---------:|---------:|---------:|------:|-----|
| 4 | 140 | 0 | 0 | 21 | 32 | 44 | 44 | 2.39 | `20261015T164131` |
| 8 | 271 | 0 | 0 | 18 | 37 | 49 | 49 | 4.58 | `20261015T164231` |
| 16 | 539 | 0 | 0 | 17 | 46 | 64 | 65 | 9.11 | `20261015T164331` |
| 32 | 1065 | 0 | 0 | 15 | 41 | 89 | 120 | 17.99 | `20261015T164432` |
| 64 | 2085 | 0 | 0 | 13 | 46 | 77 | 100 | 35.24 | `20261015T164532` |
| 128 | 3942 | 0 | 0 | 13 | 53 | 82 | 110 | 66.58 | `20261015T164632` |

### Sweep 2

6 runs, users 4 → 128, duration ~59 s per run.

| Users | Requests | Failures | Exceptions | p50 (ms) | p95 (ms) | p99 (ms) | max (ms) | req/s | Run |
|------:|---------:|---------:|-----------:|---------:|---------:|---------:|---------:|------:|-----|
| 4 | 136 | 0 | 0 | 21 | 37 | 42 | 42 | 2.30 | `20261015T164807` |
| 8 | 267 | 0 | 0 | 18 | 36 | 47 | 53 | 4.53 | `20261015T164907` |
| 16 | 527 | 0 | 0 | 16 | 38 | 51 | 59 | 8.92 | `20261015T165008` |
| 32 | 1064 | 0 | 0 | 15 | 41 | 60 | 80 | 17.94 | `20261015T165108` |
| 64 | 2076 | 0 | 0 | 13 | 42 | 73 | 85 | 35.09 | `20261015T165208` |
| 128 | 3884 | 0 | 0 | 13 | 51 | 77 | 130 | 65.59 | `20261015T165308` |

### Cross-sweep summary

| Metric | Sweep 1 | Sweep 2 |
|--------|--------:|--------:|
| Total requests | 8042 | 7954 |
| Total failures | 0 | 0 |
| Total exceptions | 0 | 0 |

Across all 13 recorded runs: **0 failures, 0 exceptions.**

## Observations

The following are direct readings of the tables above, not extrapolations:

1. **Zero failures across all 13 runs.** `locust_failures.csv` and
   `locust_exceptions.csv` are header-only in every run directory.

2. **Throughput scales with user count.** At the smallest level the
   aggregate request rate is on the order of a few req/s; at 128 users
   it is ~65 req/s. The per-user request rate is roughly constant, which
   is what the client `wait_time` dictates. The server is not the
   pacing element at any level tested.

3. **p50 does not grow with load.** Median latency sits between 13 and
   21 ms at every user level, in both sweeps. The 128-user point is
   among the *lowest* observed medians, consistent with the
   `lru_cache(maxsize=256)` on `_scan_first_visible_pass` warming up as
   more requests hit the same (satellite, ground-station) pair.

4. **p95 grows modestly.** p95 rises from ~37 ms at 4 users to ~51 ms
   at 128 users. That is a ~14 ms increase for a 32x increase in
   offered load.

5. **p99 is the widest tail.** p99 at 128 users is in the 70-80 ms
   range; the single highest observed response time in any run is
   130 ms. There is no evidence of queueing collapse.

6. **The server is not saturated at 128 users.** If it were, throughput
   would flatten before the user count stopped increasing, and p50
   would rise. Neither is observed.

## What is *not* claimed

- **Not a saturation point.** No run in this set reached the throughput
  ceiling of the backend. 128 users is the highest level tested, not
  the highest the backend can serve.
- **Not a production capacity claim.** All runs are on the local dev
  machine with a single uvicorn worker. Any deployment with a different
  worker count, host hardware, or workload mix must be re-measured.
- **Not a measurement of `/auth/*`.** The backend was started with
  `AEROGRID_DISABLE_RATE_LIMIT=1` to allow seeding; the rate limiter is
  not exercised in these runs.
- **Not a measurement of the WebSocket path.** `WS /telemetry/stream`
  is not in the locustfile endpoint mix.
- **Not a scientific-under-load test.** That is s11-7. s11-7 requires
  two concurrent `POST /discovery/run` calls with the same seed to
  return byte-identical `discovered` arrays. This baseline does not
  test determinism.
- **Not a gate.** There is no P95 pass/fail threshold in this document.
  A gate belongs in s11-6c, and setting it requires deciding what
  constitutes a regression on this workload. That decision is deferred.

## Next steps

1. **s11-6c** — worker tuning. Choose a `--workers` count for the
   launchd plist based on this baseline. Note: at 128 users the server
   is not saturated, so a worker increase would not be expected to
   change throughput under this workload. The tuning should be
   validated by re-running the sweep with the new worker count and
   comparing the p95 and req/s columns above.
2. **s11-7** — scientific gate under load. Two concurrent
   `POST /discovery/run` calls with the same seed must return
   byte-identical `discovered` arrays. This is a determinism test, not
   a latency test.

## Data location

Raw Locust CSVs: `tests/loadtest/results/<YYYYMMDDTHHMMSS>/`
Each directory contains `locust_stats.csv`, `locust_stats_history.csv`,
`locust_failures.csv`, and `locust_exceptions.csv`. 13 run
directories are present at the time this document was written.

Reproduce a single run with:

    ./scripts/run_load_test.sh <users> <spawn-rate> <duration>

For example, the 128-user, 10-users-per-second spawn, 60-second run is:

    ./scripts/run_load_test.sh 128 10 60s
