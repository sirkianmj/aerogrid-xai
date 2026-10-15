# Session Handoff — 2026-10-15

**State at this document:** `main` at commit `6b34390`.
**Supersedes:** an earlier draft of this file that existed only in a
conversation, was never written to disk, and contained multiple claims
falsified by direct inspection. Those claims and their corrections are
recorded in section 3 below so the correction is itself on the record.

---

## 1. Verified state at `6b34390`

| Item | Value | How verified |
|---|---|---|
| Repository | `https://github.com/sirkianmj/aerogrid-xai` (public) | `git remote -v` |
| Local path | `/Users/kianm.j/aerogrid-xai` | `pwd` |
| HEAD | `6b34390` on `main` | `git rev-parse HEAD` |
| Branch protection | 6 required contexts | `.github/workflows/ci.yml` lines 10, 41, 65, 137, 155, 170 |
| Backend tests | 1226 collected | `pytest --collect-only -q` |
| Backend test files | 90 | `find backend/tests -type f -name "test_*.py"` |
| Frontend test files | 29 | `find frontend/src -type f -name "*.test.*"` |
| CI (last 5 pushes) | all green | `gh run list --branch main --limit 5` |
| Python | 3.12.15 | `python3 --version` |
| Node | 20.20.2 | `node --version` |
| Postgres | 16, port 5432 | `lsof -nP -iTCP -sTCP:LISTEN` |
| Redis | 8.10.2, port 6379 | `redis-cli --version`, listener |
| Prometheus | 3.15.0, port 9090 | listener |
| Grafana | 13.2.4, port 3000 | listener |
| MinIO | **not running** | no listener on 9000/9001 |

---

## 2. Sprint 11 closed

Sprint 11 is complete: s11-1 through s11-7. See
`docs/ROADMAP_STATUS.md` for the full table.

- s11-6b produced `docs/LOAD_TEST_BASELINE.md` (177 lines).
- s11-7 produced `backend/tests/test_discovery_concurrency.py`.
- s11-6c (worker tuning) is **deferred**, not started. The baseline
  shows the server is not saturated at 128 concurrent users; there is
  no measured basis for a worker-count change.

---

## 3. Corrections to the abandoned draft

An earlier draft of a 2026-10-15 session handoff was provided as input
to this session. It was never written to disk. Direct inspection of the
repository falsified four of its claims:

| Draft claim | Verified reality | Evidence |
|---|---|---|
| "Nothing uncommitted … `git status --porcelain=v1` returned nothing" | 52 untracked load-test CSVs under `tests/loadtest/results/` | `git status --porcelain=v1` |
| "MinIO running, port 9000/9001" | No listener on 9000 or 9001 | `lsof -nP -iTCP -sTCP:LISTEN` |
| "Nothing from the load test has run yet" | 13 runs across two sweeps at `tests/loadtest/results/` | directory listing |
| "Backend 1199+ tests passing" | 1222 collected at session start; 1226 after s11-7 | `pytest --collect-only -q` |

A fifth claim in the draft — that a file `docs/SESSION_HANDOFF_2026-10-15.md`
existed — was also false; the file was never created before this one.

The draft's claims about the additive tandem receiver formula
(`backend/app/physics/receiver.py`) and the A07 rate-limit
fail-closed behaviour (`docs/SECURITY_AUDIT.md`) were verified correct
and are not affected.

---

## 4. Latent defect recorded by s11-7

Two defects surfaced while building the s11-7 concurrency test. Neither
is in the endpoint. Both are documented in the test module's docstring
and in `docs/ROADMAP_STATUS.md`.

1. **Starlette `TestClient` is unsafe under threads.**
2. **Z3 Python bindings use a process-global context.**

The endpoint is unaffected today because `/discovery/run` is
`async def` with no `await` and therefore runs serially on the event
loop under single-worker uvicorn. The Z3 finding becomes a live defect
the moment the pipeline is moved into `run_in_threadpool`. No fix
applied.

---

## 5. What remains open

Updated 2026-10-15 after Sprint 12 closed at `73c4097`.

| Item | Where |
|---|---|
| `docs/HANDOFF.md` sections 0-9 still contain stale state claims | superseded by this document |
| `frontend/src/features/Status/StatusView.tsx` has no test | only feature dir without one |
| `frontend/src/features/DesignStudio/svg/{FixedWingDetail,MultirotorDetail,SatelliteProfileSVG}.tsx` (3492 LOC) have no tests and have not been visually verified since the #127 coordinate fix | ongoing |
| Z3 global-context finding (section 4) | latent, no fix; becomes real when the discovery pipeline is moved into a threaded path |
| Frontend `App.test.tsx` mocks R3F canvas; two jsdom warnings remain | P32, P33 |
| Four scientific hypotheses in `docs/SCIENTIFIC_CLAIMS.md` remain UNCOVERED (H1, H3, H4, H7) | by the project's own rule, these are **invalid** |
| Four hypotheses remain PARTIAL (H2, H8, H10, H11) | gaps named in SCIENTIFIC_CLAIMS.md |
| s3-8 (PWL soundness direction) | status decision needed; tracker says PENDING |
| Phase 2 remainder: flip encoder default to physics variant (P28); whole-network flow balance | not started |
| s11-6c (worker tuning) | deferred with rationale; baseline shows no saturation |

---

## 6. Where to go next

Sprint 11 and Sprint 12 are complete. The next engineering decisions,
in descending order of scientific value:

1. **Fix the Z3 global-context finding.** It is latent today; it
   becomes a real defect the moment the discovery pipeline is moved
   into `run_in_threadpool` or any other threaded path. Two options:
   a `threading.Lock` around `encode_architecture` (simple, serialises
   the encoder) or a per-thread Z3 context (keeps parallelism, more
   work). This is a real engineering decision; the evidence is in the
   s11-7 test module's docstring and in the s11-7 PR body.

2. **Address the four UNCOVERED scientific hypotheses (H1, H3, H4,
   H7).** By the project's own s9-7 rule, they are invalid until a
   test exists whose failure would falsify them. Each requires a
   specific experiment: H1 needs a position-only tracking baseline;
   H3 needs a weather-independent scheduling arm; H4 needs decision
   robustness under environmental noise; H7 needs annual availability
   computed across regions. Real scientific work, probably weeks.

3. **Frontend test gaps.** `StatusView.tsx` has no test; the three
   large SVG drawings have no tests. Smaller scope, mechanical.

4. **s3-8 status decision.** The PWL soundness direction question in
   `docs/DID/STR.md` section 6.3.7 is covered by `test_fuzz_soundness.py`
   in the direction that is sound under the spec's literal encoding,
   but the tracker still says PENDING. A decision, not code.

Do not begin any of these by trusting `docs/HANDOFF.md`'s state
claims. Trust this document and `docs/ROADMAP_STATUS.md`.
