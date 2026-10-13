# AeroGrid-XAI Roadmap Status

Authoritative tracker of roadmap completion. Updated on every merged PR.

Runtime: native macOS, Miniforge (conda-forge). No Docker, no Kubernetes,
no cloud VMs. Z3 is the only formal-verification tool; no Lean.

Branch protection on `main`:
- Required checks: backend, frontend, formal-verification, cla-check
- `enforce_admins: true`, `strict: true`
- Force-push and branch deletion blocked
- Conversation resolution required
- Zero required approving reviews (solo maintainer)

## Phase 0 — Repository, Legal & Commercial

| ID | Task | Status |
|----|------|--------|
| p0-1 | Monorepo structure | COMPLETE |
| p0-2 | Dual-license files (AGPL-3.0 + Commercial EULA) | COMPLETE (external counsel review skipped by maintainer, documented in LICENSING_MATRIX) |
| p0-3 | Contributor License Agreement | COMPLETE (CLA.md + CI enforcement) |
| p0-4 | README commercial section | COMPLETE (commercial contact is a placeholder) |
| p0-5 | Component license matrix | COMPLETE |
| p0-6 | Defensive publication record | COMPLETE (docs/DEFENSIVE_PUBLICATION.md) |

## Sprint 0 — Foundation & CI/CD

| ID | Task | Status |
|----|------|--------|
| s0-1 | GitHub repo + branch protection | COMPLETE (4 required checks: backend, frontend, formal-verification, cla-check) |
| s0-2 | Dual-license + CLA + LICENSING_MATRIX | COMPLETE |
| s0-3 | Miniforge env `aerogrid` | COMPLETE |
| s0-4 | Native PostgreSQL + Redis + scripts | COMPLETE (scripts/start_services.sh, stop_services.sh, status_services.sh) |
| s0-5 | Backend FastAPI scaffold | COMPLETE |
| s0-6 | Frontend scaffold | COMPLETE |
| s0-7 | CI pipeline (backend, frontend, formal-verification, cla-check) | COMPLETE |
| s0-8 | Notebook 01 — TRL benchmark validation | COMPLETE (PR #2) |
| s0-9 | Cascaded link budget scientific gate | COMPLETE (PR #3) |

## Sprint 1 — Digital Twin Core: Orbital Mechanics

| ID | Task | Status |
|----|------|--------|
| s1-1 | Skyfield integration | COMPLETE (PR #4) |
| s1-2 | TLE ingestion + propagation | COMPLETE (PR #4) |
| s1-3 | Visibility window calculator | COMPLETE (PR #5) |
| s1-4 | Eclipse period detection | COMPLETE (PR #5) |
| s1-5 | Geographic region model | COMPLETE (PR #6) |
| s1-6 | Notebook 02 — LEO vs GEO visibility | COMPLETE (PR #6) |
| s1-7 | No hard-coded positions | COMPLETE (PR #6) |

## Sprint 2a — Stage A receiver stack

| ID | Task | Status |
|----|------|--------|
| s2-1 | PLC efficiency model eta_PLC(T) | COMPLETE (PR #8) |
| s2-2 | TE efficiency model eta_TE(T) | COMPLETE (PR #8) |
| s2-3 | Corrected attribution: Sb2Se3 in thermal conduction, NOT Seebeck | COMPLETE (PR #8) |

## Sprint 2b — Two-node thermal model + runaway boundary

| ID | Task | Status |
|----|------|--------|
| s2-4 | Two-node lumped thermal model (dT_PLC/dt, dT_TE/dt) | COMPLETE (PR #9) |
| s2-5 | Thermal runaway boundary P_max(T_amb, v) | COMPLETE (PR #9) |

## Sprint 2c — Efficiency surface + dimensional consistency

| ID | Task | Status |
|----|------|--------|
| s2-6 | Notebook 03 — Efficiency surface eta(P, T, v) | COMPLETE (PR #11) |
| s2-7 | Scientific gate: dimensional consistency | COMPLETE (PR #11) |

## Sprint 3 — Stage B: PWL-SMT Constraint Encoding

| ID | Task | Status |
|----|------|--------|
| s3-1 | PWL approximation builder | COMPLETE (PR #12) |
| s3-2 | Error tracker (epsilon per constraint family) | COMPLETE (PR #12) |
| s3-3 | Incremental Linearization encoding to SMT-LIB | COMPLETE (PR #13) |
| s3-4 | Hierarchical decomposition (k=5-15 intra-cluster + inter-cluster flow) | COMPLETE (PR #14) |
| s3-5 | Regulatory constraint encoding (ANSI Z136.1 MPE + FCC Part 1.1310) | COMPLETE (PR #15) |
| s3-6 | Notebook 04 — PWL accuracy vs. segments | COMPLETE (PR #16) |
| s3-7 | Notebook 05 — Hierarchical vs. monolithic Z3 | COMPLETE (PR #17) — see gate reformulation below |
| s3-8 | Scientific gate: SAT verdict is conservative | PENDING — see gate note below |

### s3-7 gate reformulation (Rev. 2 → Rev. 3)

The Rev. 2 roadmap gate for s3-7 was:

> Hierarchical solves >50 nodes; monolithic times out.

The measurement in Notebook 05 (PR #17) does not reproduce this claim
on satisfiable, structurally-independent cluster constraints. Measured
hierarchical-versus-monolithic ratios were 0.78x–0.96x — hierarchical
10–20% slower — because Z3's internal preprocessing detects structural
independence and decomposes the problem internally. External per-cluster
decomposition adds Python-side setup cost without saving solve time.
The spec's asymptotic claim (Section 34.3, "SMT solving is exponential
in the worst case") is correct in principle but is not reproduced when
per-cluster subproblems solve in ~10 ms each.

The reformulated gate, which the measurement supports, is:

> (a) Hierarchical solve time scales linearly with cluster count.
> (b) Composition overhead is bounded and small in absolute terms
>     (sub-second at 64 clusters).
> (c) The Section 34.3 soundness invariant — SAT iff every cluster SAT
>     and inter-cluster flow SAT — is preserved. This is covered by
>     15 tests in backend/tests/test_hierarchical.py.

Reason for reformulation: the original claim is a design-intent
statement, not a measured property. Replacing it with a measured claim
is consistent with the epistemic hierarchy (Section 21) and with the
project rule that any scientific claim not covered by test is invalid
(roadmap s9-7).

### s3-8 gate note (pending)

The Rev. 2 roadmap gate for s3-8 is:

> SAT verdict is conservative — Fuzz test against random architectures —
> Never falsely declares infeasible architecture feasible.

The literal claim is not consistent with the PWL direction selected by
Section 34.2 of the spec. Section 34.2 writes f_hat(x) <= f(x) and calls
it a "sound over-approximation". Under that direction:

  - UNSAT is definitive: an empty encoded region implies an empty true
    region.
  - SAT is necessary but not sufficient: the encoded region is a
    superset of the true region, and a SAT witness may still violate
    the true constraint.

Under the spec's literal direction, the correct soundness statement is
"UNSAT never falsely declares a feasible architecture infeasible", not
"SAT never falsely declares an infeasible architecture feasible". The
discrepancy is documented in the docstrings of
backend/app/verification/pwl.py and backend/app/verification/encoder.py.

s3-8 will be implemented in the next commit. The plan is to fuzz-test
the UNSAT direction (the direction that is sound under the spec's
literal encoding) and to record the direction question prominently in
the test module rather than silently resolving it. If the project
requires the strict "SAT is conservative" claim, the fix is to flip
the PWL direction from f_hat <= f to f_hat >= f. That is a localized
change to the sampling loop in pwl.py and would require re-running
every downstream test.

## Sprint 4 — Stage C: Generative Discovery with UNSAT-Core Feedback

| ID | Task | Status |
|----|------|--------|
| s4-1 | Architecture grammar (context-free) | COMPLETE (PR #18) |
| s4-2 | Candidate generation (random derivations + parameter attachment) | COMPLETE (PR #18) |
| s4-3 | UNSAT-core extraction (z3.get_unsat_core()) | COMPLETE (PR #18); minimal-core guarantee added in PR #41 |
| s4-4 | UNSAT-core-to-grammar-feature attribution (inventive core) | COMPLETE (PR #19) |
| s4-5 | Conflict-directed mutation | COMPLETE (PR #19) |
| s4-6 | NSGA-II integration (Pareto over C,R,E,N,T,U) | COMPLETE (PR #20); closed-loop composition with real Stage B encoder added in PR #43 |
| s4-7 | Notebook 06 — Unsat-core feedback ablation | COMPLETE (PR #21); uses synthetic 2-constraint fixture; upgrade to real encoder is open |
| s4-8 | Scientific gate: attribution deterministic and reproducible | COMPLETE (PR #21) |

### s4-6 composition note

Until PR #43, `run_nsga2` called `mutate_random` unconditionally and never
invoked Z3, extracted a core, or built a `ConflictProneTable`. The
attribution → conflict-directed-mutation mechanism existed and was tested
in isolation (`test_h9_convergence.py`, Notebook 06), but was not composed
into the production discovery loop.

PR #43 adds:

- `backend/app/verification/architecture_encoder.py` — real Stage B encoder
  emitting flow-balance, supply-cap, demand-floor, and regulatory (ANSI
  Z136.1 / FCC 1.1310) constraints, each tagged with originating grammar
  features.
- `backend/app/discovery/loop.py` — `run_clear_d_loop` composes
  encode → check → attribute → mutate (by rule) → NSGA-II select across
  generations.

`nsga2.py` is unchanged; its existing tests still pass.

## Sprint 5 — Stage D: Two-Tier XAI Controller

| ID | Task | Status |
|----|------|--------|
| s5-1 | Tier 1 rule list / GAM / bounded tree | COMPLETE (PR #22) |
| s5-2 | Tier 2 surrogate — atmospheric loss | COMPLETE (PR #23) |
| s5-3 | Tier 2 surrogate — trajectory prediction | COMPLETE (PR #24) |
| s5-4 | Static analyzer: Tier 2 never reaches action interface | COMPLETE (PR #25) |
| s5-5 | Explanation generator (literal trace output) | COMPLETE (PR #25) |
| s5-6 | Notebook 07 — Explanation fidelity test | COMPLETE (PR #26) |
| s5-7 | Scientific gate: hard invariant statically verified | COMPLETE (PR #25) |

## Sprint 6 — Stage E: Closed-Loop Refinement

| ID | Task | Status |
|----|------|--------|
| s6-1 | Bayesian parameter update | COMPLETE (PR #35) |
| s6-2 | PWL tightening/relaxing based on SAT/UNSAT vs observed | COMPLETE (PR #36) |
| s6-3 | Digital Twin state comparison | COMPLETE (PR #37) |
| s6-4 | Notebook 08 — Closed-loop convergence | COMPLETE (PR #38); Kalman linearization fix in PR #40 |
| s6-5 | Scientific gate: loop is causal | COMPLETE (PR #39) |

## Sprint 7 — React Mission-Control UI

COMPLETE. Six tasks, eleven PRs (#59 through #69).

| ID | Task | Status |
|----|------|--------|
| s7-1 | Extend Sprint-0 design system | COMPLETE (PR #59) — Tailwind 4, design tokens, WCAG 2.1 AA contrast test, EpistemicHierarchyBadge with all seven Section 21 categories |
| s7-2 | 3D Globe (Three.js) | COMPLETE (PRs #62, #63) — backend orbital endpoints and frontend Globe scene |
| s7-3 | Real-time telemetry dashboard (WebSocket) | COMPLETE (PRs #66, #67) — `WS /telemetry/stream` with a bounded client-side ring buffer of 1000 samples |
| s7-4 | XAI Trace Panel | COMPLETE (PRs #60, #61) — `POST /decisions/charge` and the Section 15.5 trace panel |
| s7-5 | Digital Twin state view | COMPLETE (PRs #64, #65) — state, trajectory, and discrepancy endpoints plus an inline SVG transient chart |
| s7-6 | Trade Space explorer | COMPLETE (PRs #68, #69) — NSGA-II endpoint and a parallel-coordinates Pareto explorer |
| s7-7 | UI gate: every output tagged per Section 21 | PARTIAL — the `EpistemicBadge` component exists and every new panel wraps its content in `TaggedOutput`; a full UI audit remains |
| s7-8 | Frontend CI extended with new components | COMPLETE (implicitly) — the existing frontend CI job runs oxlint + tsc -b + vitest + vite build, and all four are green on the new code |
| s7-9 | UI does not obscure epistemic status | PARTIAL — the badge is rendered on every panel; a written audit remains |

### Frontend test count

0 (beyond scaffold) at ef428bf, 153 at 33d94f9.

### Backend additions during Sprint 7

Four new API packages: `app/physics/api.py`, `app/telemetry/api.py`,
`app/digital_twin/api.py`, `app/tradespace/api.py`. Twelve HTTP routes
and one WebSocket route. All registered in `app/main.py`.

## Sprint 9 — Master Test Harness (partial)

| ID | Task | Status |
|----|------|--------|
| s9-5 | Notebook 10 — Full CLEAR-D loop demonstration | COMPLETE (PR #46) — mechanism-level demonstration at 3.29x |
| s9-1 | Master test harness `tests/master_test.py` | Not started |
| s9-2 | Scientific validation suite | Not started |
| s9-3 | Z3 verification end-to-end | Not started |
| s9-4 | XAI fidelity audit | Not started |
| s9-6 | CI: nightly notebook reproducibility | Not started |
| s9-7 | Scientific gate: Master test passes 100% | Not started |

s9-5 was the notebook that the roadmap scheduled as the end-to-end
demonstration of CLEAR-D. The mechanism demonstration is complete and
committed; the broader master test harness (s9-1 through s9-4, s9-6,
s9-7) remains. Note that the notebook measures the H9 hypothesis at
the mechanism level (repair rate on infeasible architectures) rather
than the loop level, because the generator connectivity fix introduced
in the same PR made the loop-level comparison non-informative on the
current seed distribution. Both facts are documented in the notebook
itself and in the PR description.

## Phase 2 — Multi-Modal Wireless Power Model (in progress)

This is Phase 2 of the specification's Development Phases (Section 25),
not to be confused with roadmap Rev. 2's Sprint 10 (Q1 article and
DARPA DID documentation). Prior PR titles labelled this work "Sprint
10"; the label was a documentation error. The correct name is Phase 2.

The specification's Development Phases (Section 25) list the Multi-Modal
Wireless Power Model as Phase 2, with physics modules that were not yet
built. This sprint tracks that work.

| Task | Status |
|------|--------|
| `physics/atmosphere.py` — Kruse-Kim extinction with Beer-Lambert transmittance | COMPLETE (PR #47) |
| Rewire `control/tier2.py` to call `physics/atmosphere.py` | COMPLETE (PR #50) |
| `physics/beam.py` + `build_physical_link_budget` — Gaussian beam geometry | COMPLETE (PR #49) |
| `physics/rectenna.py` — RF-to-DC conversion chain | COMPLETE (PR #51) |
| Encoder physics integration design doc | COMPLETE (PR #52) |
| `encode_architecture_with_physics` — additive physics extension | COMPLETE (PR #53) |
| `physics/geometry.py` extracted; rectenna zero-density fix | COMPLETE (PR #54) |
| Generator LOS-compliant placement + pole-corrected latitude | COMPLETE (PR #56) |
| Generator physics-aware link kind sampling | COMPLETE (PR #57) |
| Flip encoder default to physics variant (PR-C) | Not started |
| Whole-network flow balance in the physics extension | Not started |

## Sprint 8 — in progress (6 of 9 complete)

Sprint 8 (multi-tenant SaaS) at `faa9cab`:

| Task | Status | PR |
|------|--------|----|
| s8-1 MinIO install + service scripts | COMPLETE | - |
| s8-2 PostgreSQL 16 + Redis 8 startup | COMPLETE | - |
| s8-3 PostgreSQL row-level security | COMPLETE | #71 |
| s8-4 Tenant JWT middleware | COMPLETE | #72 |
| s8-5a Stripe library | COMPLETE | #73 |
| s8-5b Stripe routes + webhook + idempotency | COMPLETE | #74 |
| s8-6 Quota management | COMPLETE | #75 |
| s8-7 Admin panel (React) | NOT STARTED | - |
| s8-8 Notebook 09 (multi-tenant isolation) | NOT STARTED | - |
| s8-9 Scientific gate: DB-level isolation audit | NOT STARTED | - |

Branch protection now requires all five CI contexts, including
`rls-isolation`. The four DB-backed test modules
(test_rls_isolation.py, test_saas_routes.py,
test_saas_billing_routes.py, test_saas_quota.py) run in that job
against an ephemeral PostgreSQL 16 service container and the job
fails on any skip.
- Sprint 9 builds the master test harness and
  `notebooks/10_clear_d_end_to_end.ipynb`. The composition that notebook
  was scheduled to produce is already in place as of PR #43; the notebook
  will wrap `run_clear_d_loop` with the full physics pipeline and produce
  publication-quality results.

## Documentation drift resolved

- `docs/HANDOFF.md` written from the verified state at commit `aab8a42`.
- `CHANGELOG.md` updated through Sprint 10.
- This file's prior "Sprints 4–12 not started" statement is corrected above.

## Outstanding

- **P5** — Han et al. citation in `physics/benchmarks.py` lacks DOI or
  volume; paper existence unverified. Requires a browser check.
- **s3-8** — tracker says PENDING; `test_fuzz_soundness.py` exists and
  tests the sound direction (UNSAT definitive) rather than the literal
  Rev. 2 wording. Status decision needed.
- **P14** — `UAV_ASSUMED_TRANSMIT_W = 20.0` and
  `NODE_DEFAULT_DEMAND_W = 15.0` in the new encoder are `[ESTIMATED]`.
- **P15** — `Hybrid_Link` emits both laser-MPE and RF-MPE constraints
  simultaneously (modelling simplification).
- **P16** — `generator.encode_architecture_to_z3` placeholder superseded
  but not removed.
- **P17** — Notebook 06 could be upgraded to use the real encoder.
- **P20** — upstream anyio `BlockingPortal` DeprecationWarning.
- **P21** — Kruse-Kim coefficients in `physics/atmosphere.py` cited but
  not verified against source PDFs; browser check required.
- **P22** — `tier2.py` still uses its own unsourced coefficients; rewire
  to `physics/atmosphere.py` is the next Phase 2 task.
- **P23** — cascaded link budget has four bare-float inputs; spec Section
  8.4 requires thirteen physical inputs.
- **P24** — rectenna model absent; only PV-TE tandem receiver exists.
- **P25** — encoder does not invoke physics modules; feasibility is
  driven only by flow balance and MPE.
- **P26** — the generator does not verify combined UAV supply vs. demand.
  Ten of thirty sampled architectures are UNSAT for this reason.
- **P28** — the physics encoder remains opt-in. `run_clear_d_loop` uses
  the base encoder; flipping is design doc Decision 6, still pending.
- **P29** — `visible_cap_fraction=0.10` places UAVs at feasible but not
  boundary-pushing ranges. Documented modelling choice.
- **P30** — `atmospheric_path_length_m` over-counts for chords that exit
  the top of the shell between two in-shell endpoints. Latent; not
  triggered by the generator.
- **P31** — Frontend production bundle is 1.20 MB / 330 KB gzipped,
  dominated by Three.js. Code-splitting Globe into a lazy chunk is a
  follow-up.
- **P32** — The Globe test mocks the R3F Canvas, producing jsdom
  element-casing warnings for R3F intrinsics. Cosmetic.
- **P33** — The Telemetry test's fake socket pushes messages outside
  React's event flow, producing an act() warning. Tests pass.
- **P34** — Sprint 7 s7-7 and s7-9 are partial: the badge infrastructure
  and per-panel tagging exist, but no formal UI audit has been done.
