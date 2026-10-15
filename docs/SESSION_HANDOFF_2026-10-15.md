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

Updated 2026-10-15 after the post-Sprint-12 hypothesis audit closed at
`3480461`.

| Item | Where |
|---|---|
| `docs/HANDOFF.md` sections 0-9 still contain stale state claims | superseded by this document |
| `frontend/src/features/Status/StatusView.tsx` has no test | only feature dir without one |
| `frontend/src/features/DesignStudio/svg/{FixedWingDetail,MultirotorDetail,SatelliteProfileSVG}.tsx` (3492 LOC) have no tests and have not been visually verified since the #127 coordinate fix | ongoing |
| Z3 global-context finding (section 4) | **first-touch race fixed** in PR #145 (`main.py` forces `z3.main_ctx()` at import boundary). Full per-context fix deferred with pre-registered criteria in `test_z3_single_context_contract.py`. |
| Frontend `App.test.tsx` mocks R3F canvas; two jsdom warnings remain | P32, P33 |
| **H4** is FALSIFIED | New status in `SCIENTIFIC_CLAIMS.md`; the Tier 2 interval is constant-width. See §5c. |
| H7 is UNCOVERED (capability absent) | `docs/H7_AVAILABILITY_SCOPE.md` names the six components that would have to be built |
| Six hypotheses remain PARTIAL (H1, H2, H3, H8, H10, H11) | gaps named in SCIENTIFIC_CLAIMS.md |
| SPEC §27 reconciliation with SCIENTIFIC_CLAIMS.md | H4 is falsified; H7 is capability-absent. Highest-priority non-code task. |
| s3-8 (PWL soundness direction) | status decision needed; tracker says PENDING |
| Phase 2 remainder: flip encoder default to physics variant (P28); whole-network flow balance | not started |
| s11-6c (worker tuning) | deferred with rationale; baseline shows no saturation |

---

## 5b. Z3 finding — corrected and closed at #145

The s11-7 PR originally reported the Z3 defect as "context is
thread-local." That was **wrong**. Direct experiment (three diagnostic
scripts, recorded in PR #145's body) established:

| Experiment | Sequence | Result |
|---|---|---|
| 1 | Two threads race `z3.main_ctx()` with no prior Z3 use | **Different** contexts |
| 2 | Main thread calls it first, then two workers call it | **Same** context (worker = main) |
| 3 | Explicit `z3.Context()` rejects cross-context arithmetic | Confirmed as expected |

Corrected diagnosis: **Z3's main context is a process-global
singleton with a first-touch race.** After any thread has called
`main_ctx()` once, every subsequent call returns the same context.

Fix applied at #145: `backend/app/main.py` calls `z3.main_ctx()` once,
during FastAPI module import, before `app = FastAPI(...)`. The import
is synchronous, so no request handler thread can race it.

Contract test: `backend/tests/test_z3_single_context_contract.py`
(3 tests). Its module docstring carries the pre-registered acceptance
criteria for the deferred full per-context fix (5 modules, ~60 call
sites), so the deferral is bounded.

---

## 5c. Post-Sprint-12 hypothesis audit (PRs #147-#150)

Five hypotheses moved off UNCOVERED. One — H4 — moved to a new status,
FALSIFIED, because the test exercises the claim on a declared scope
and the claim does not hold there.

| Hypothesis | Before | After | Evidence |
|---|---|---|---|
| H1 | UNCOVERED | PARTIAL | `test_h1_predictive_tracking.py` — predictive beats position-only on held-heading motion (gain +0.45 at L=2s, w=17m); "within disclosed uncertainty" clause not exercised |
| H2 | PARTIAL (primitives only) | PARTIAL (mechanism covered) | `test_h2_nsga2_baseline.py` — joint beats split on all 5 seeds; mean relative hypervolume gap ~0.35%; "resilience" per se not tested |
| H3 | UNCOVERED | PARTIAL | `test_h3_atmosphere_scheduling.py` — aware reduces failures (0.003 vs 7.155 per schedule); "optimization" is greedy max-forecast |
| **H4** | **UNCOVERED** | **FALSIFIED** | `test_h4_uncertainty_decisions.py` — Tier 2 interval is constant-width; aware policy algebraically identical to a shifted point policy. **The claim cannot hold on this design.** |
| H7 | UNCOVERED | UNCOVERED (capability absent) | `docs/H7_AVAILABILITY_SCOPE.md` — annual availability + regional aggregation do not exist |

**H4 is the first FALSIFIED status in the project.** The specification's
Section 27 H4 statement — *"Uncertainty-aware decisions are more
robust under environmental variability than point estimates"* — is
withdrawn as a property of the current system. Reconciling SPEC §27
with `SCIENTIFIC_CLAIMS.md` is now the highest-priority non-code task.

**H7's relabel** matters semantically. Everywhere else, UNCOVERED
means "we have the mechanism, we have not tested it." For H7 it means
"we do not have the mechanism." No test can move H7 off UNCOVERED
without building the capability first.

---

## 6. Where to go next

Sprint 11 and Sprint 12 are complete. The Z3 finding is closed (see
§5b). The next engineering decisions, in descending order of
scientific value:

1. **Reconcile SPEC §27 with `docs/SCIENTIFIC_CLAIMS.md`.** H4 is
   now FALSIFIED; H7 is UNCOVERED (capability absent). Either the
   spec statement is wrong or it is intended as a research direction
   and should be relabelled. A spec that states falsified claims is
   worse than one that states no claims. This is the single most
   important non-code task.

2. **Frontend test gaps.** `StatusView.tsx` has no test; the three
   large SVG drawings (`FixedWingDetail.tsx`, `MultirotorDetail.tsx`,
   `SatelliteProfileSVG.tsx`, 3492 LOC total) have no tests and no
   browser verification since #127. Smaller scope, mechanical, safe.

3. **s3-8 status decision.** The PWL soundness direction question in
   `docs/DID/STR.md` §6.3.7 is covered by `test_fuzz_soundness.py` in
   the sound direction, but the tracker says PENDING. A decision, not
   code.

4. **H7 build-out, if the direction is chosen.** Six components,
   6-9 sessions. See `docs/H7_AVAILABILITY_SCOPE.md`. Do not begin
   without an explicit decision that H7 is a research direction.

5. **Phase 2 remainder.** Flip encoder default to the physics variant
   (P28); add whole-network flow balance.

6. **The deferred Z3 per-context fix.** Pre-registered criteria in
   `backend/tests/test_z3_single_context_contract.py`. Not urgent
   until something takes the pipeline off the single-threaded path.

Do not begin any of these by trusting `docs/HANDOFF.md`'s state
claims. Trust this document and `docs/ROADMAP_STATUS.md`.
