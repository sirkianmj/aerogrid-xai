# Changelog

All notable changes to AeroGrid-XAI are documented here.
This project adheres to Semantic Versioning.

## [Unreleased]

### Added (Instrument — PRs #80 through #102)

UI and API work after Sprint 10 that turned the platform into the
instrument Section 4 of the specification describes:

- `GET /mission/state` — a coherent scenario composed from the real
  SGP4 propagation, Kruse-Kim transmittance, Z3 SAT/UNSAT verdict on
  a generated architecture, a one-generation CLEAR-D snapshot, and a
  Tier 1 decision trace. New router mounted in `backend/app/main.py`.
- Mission Control panel — the Section 4 pipeline rendered as a live
  vertical instrument with per-stage status pills (`wired` / `partial`
  / `pending` / `offline`).
- CLEAR-D Discovery dashboard — the loop's unsat-core-to-grammar
  attribution trace exposed via `POST /discovery/run` and rendered in
  the UI. `run_clear_d_loop` gained an optional `trace` parameter
  (default `None`, existing callers unchanged).
- Animated Globe — satellite picker, time scrubber, play/pause, and
  speed selector. Uses the existing `/orbital/track` endpoint with
  caller-controlled `t_start` / `t_end` / `step_seconds`.
- FANET graph — layered topology rendered from the architecture's
  `node_list` and `link_list`. `ArchitectureSummary` extended with
  both (additive, empty defaults).
- Mission configuration bar + `MissionProvider` context — one source
  of truth for the mission, driving every panel that consumes it.
  `/mission/state` gained `ground_lat_deg`, `ground_lon_deg`,
  `transmitter_power_w` query parameters.
- Ground-anchored CLEAR-D — `GeneratorConfig` gained
  `ground_station_lat_deg` / `ground_station_lon_deg` so the loop's
  architectures are rooted at the configured ground station.
- Tier 2 uncertainty bands — the calibrated interval around
  atmospheric transmittance is surfaced in the mission state and
  rendered in Mission Control.

The TradeSpace frontend client was fixed to send its `Authorization`
header (previously 401 after s8-6 required auth on `/tradespace/run`).
A `SessionBar` was added so a JWT can be pasted without opening
DevTools.

Backend test count 990 -> 1106. Frontend 163 -> 224.

### Added (Sprint 8 - PRs #71 through #79)
- PostgreSQL row-level security on `missions` (PR #71). Application
  role `aerogrid_app` with NOSUPERUSER NOBYPASSRLS; `tenant_session`
  switches via `SET LOCAL ROLE` and sets `app.tenant_id` via
  `set_config(..., true)`. Policy uses
  `NULLIF(current_setting('app.tenant_id', true), '')::uuid`.
- Tenant JWT middleware: HS256 tokens, roles viewer < admin < superadmin,
  `require_tenant` and `require_role(min)` FastAPI dependencies,
  `GET /saas/whoami` and `GET /saas/mission-count` (PR #72).
- Stripe billing library: `StripeClient` protocol, `LiveStripeClient`,
  `FakeStripeClient`, `stripe_config` (PR #73).
- Stripe routes and webhook handler: `POST /saas/checkout-session`,
  `GET /saas/subscription`, `POST /saas/webhook/stripe` with HMAC
  verification and PostgreSQL idempotency on event ID (PR #74).
- Quota management: `Metric` (z3_solves, tradespace_runs, clear_d_runs),
  `Plan` (free, pro, enterprise), `PLAN_LIMITS`, `PostgresQuotaStore`,
  `FakeQuotaStore`, `consume` with HTTP 429 and `Retry-After` on limit
  exceedance; wired into `POST /tradespace/run` (PR #75).
- Fifth CI job `rls-isolation` (added during s8-3, promoted to a
  required branch-protection context after s8-6).
- Database-level isolation audit (`docs/ISOLATION_AUDIT.md`); migration
  `004_tenants_least_privilege.sql` revokes `SELECT` on `tenants` from
  `aerogrid_app`, closing finding F-1 (PR #77).
- Notebook 09 (`notebooks/09_tenant_isolation.ipynb`): provisions two
  tenants, exercises every tenant-scoped endpoint with each token, and
  proves at the database layer that A cannot read B (PR #78).
- Admin routes: `GET /saas/admin/tenants` and
  `GET /saas/admin/tenants/{tenant_id}/usage`, both superadmin-only
  (PR #79).
- AdminPanel frontend feature: superadmin UI reading from
  `localStorage`; handles 401, 403, 404, and network errors; 10 new
  tests (PR #79).
- Branch protection: `rls-isolation` promoted to a required context.
- Backend test count 881 -> 990; frontend 153 -> 163.

### Added (Sprint 7 - PRs #59 through #69)
- Design system: Tailwind 4, design tokens, WCAG 2.1 AA contrast
  verification, EpistemicHierarchyBadge with all seven Section 21
  categories (PR #59).
- 3D Globe: backend orbital endpoints (`/orbital/satellites`,
  `/orbital/track`, `/orbital/visibility`) and frontend Three.js scene
  with geodetic conversion library (PRs #62, #63).
- Real-time telemetry: WebSocket endpoint `WS /telemetry/stream` and
  frontend live panel with a bounded ring buffer of 1000 samples
  (PRs #66, #67).
- XAI Trace Panel: `POST /decisions/charge` endpoint and Section 15.5
  trace panel (PRs #60, #61).
- Digital Twin state view: `/digital-twin/state`, `/trajectory`,
  `/discrepancy` endpoints and a panel with an inline SVG thermal
  transient chart (PRs #64, #65).
- Trade Space explorer: `POST /tradespace/run` running NSGA-II and a
  parallel-coordinates Pareto front visualization (PRs #68, #69).
- Backend test count 813 -> 881; frontend test count 0 -> 153.

### Added (Phase 2 - PR #57, previously labelled Sprint 10)
- Generator physics-aware link kind sampling. Link kinds are sampled
  from the set that is physically viable at the final placed geometry,
  not uniformly over all three kinds. Algorithm order fixed: kinds,
  then base positions, then topology without link kinds, then UAV
  placement inside anchor caps, then link kind selection. Measured
  effect on the 30-seed characterization: 0/30 SAT before, 20/30 SAT
  after.
- `SATELLITE_GEO` removed from the generator's source-kind pool.
  Documented: a 2 cm beam at 35,800 km spreads to a 600 m radius; a
  metre-scale receiver captures 1e-4 of the beam, five orders of
  magnitude below viability. Terminal remains in the grammar.
- `visible_cap_fraction: float = 0.10` on `GeneratorConfig`. Places
  UAVs close enough to their anchor source that the physical chain
  closes at the placement geometry.

### Added (Phase 2 - PR #56)
- Generator LOS-compliant placement: source-kind nodes uniformly on
  the sphere, UAVs inside their anchor's visible cap. `require_line_of_sight`
  flag enables the historical wide-placement ablation.
- Pole-corrected latitude sampling: `sin(lat)` uniform instead of
  `lat` uniform. Measured E[|lat|] now matches 32.70 degrees.
- `LEO` power range corrected from (50, 1000) to (1000, 20000) W.
- Receiver aperture ranges for all three link kinds corrected from
  centimetres to metres.
- `physics/geometry.py` extracted; `sample_direction_in_visible_cap`
  and `visible_cap_half_angle_rad` available to discovery modules.

### Added (Phase 2 - PRs #47 through #54)
- `physics/atmosphere.py`: Kruse-Kim extinction with Beer-Lambert
  transmittance and 32 tests.
- `physics/beam.py`: Gaussian beam geometry and pointing loss.
- `physics/rectenna.py`: peaked RF-to-DC efficiency with McSpadden
  peak values.
- `build_physical_link_budget`: cascaded link budget from geometry.
- `tier2.py` rewire to `physics/atmosphere`.
- `encode_architecture_with_physics`: additive physics extension.
- `docs/ENCODER_PHYSICS_INTEGRATION.md`: seven design decisions.

### Added (Phase 2 - PR #47, previously labelled Sprint 10)
- `physics/atmosphere.py`: atmospheric extinction and transmittance.
  Kruse (1962) aerosol model with Kim et al. (2001) low-visibility
  refinement; Beer-Lambert transmittance. Coefficients carry explicit
  [SOURCED] / [ESTIMATED] tags. Range of validity enforced (400-1550 nm,
  0.05-100 km visibility); out-of-range inputs raise ValueError rather
  than silently extrapolating. 32 tests.

### Added / Fixed (Sprint 9 - PR #46)
- MPE gating by target-node kind. `EncoderConfig.human_accessible_kinds`
  (default `{GROUND_STATION}`); MPE fires only when the link target is
  human-accessible. Canary test verifies the false-positive failure mode
  is real when the set is misconfigured.
- Generator connectivity guarantee: `generate_architecture` now emits
  one source->UAV repair link per UAV node before generating extra
  random links, so no UAV is structurally unpowerable. Measured effect
  on a fixed 30-seed audit: 0/30 sat -> 24/30 sat.
- Constrained selection in `run_clear_d_loop`: feasible individuals
  always dominate infeasible ones; NSGA-II orders within each subset.
  `nsga2.py` unchanged.
- `ClearDLoopConfig.use_conflict_directed` flag (default True) for the
  H9 control arm.
- `notebooks/10_clear_d_end_to_end.ipynb`: CLEAR-D repair mechanism
  demonstration on real Stage B physics. Conflict-directed arm repaired
  391/500 infeasible architectures (78.2%); random arm 119/500 (23.8%);
  ratio 3.29x. Gate is strict inequality with a 1.5x minimum margin and
  an explicit vacuous-gate guard.

### Added (Sprint 7 - PR #45)
- `EncoderConfig` in `architecture_encoder.py`: `uav_assumed_transmit_w`,
  `node_default_demand_w`, `human_accessible_kinds` all tunable by
  construction. Both [ESTIMATED] values carry explicit docstring flags.
- Hybrid MPE conservatism documented: a Hybrid_Link must satisfy both
  laser and RF MPE limits because it may switch modality at any time.
- `generator.encode_architecture_to_z3` docstring marked SUPERSEDED,
  pointing at `architecture_encoder.encode_architecture`.

### Added (Sprint 7 - PR #43)
- Real Stage B encoder (backend/app/verification/architecture_encoder.py):
  flow-balance, supply-cap, demand-floor, and regulatory (ANSI Z136.1 laser
  MPE / FCC Part 1.1310 RF) constraints, each tagged with the grammar
  features of the originating node or link.
- CLEAR-D closed-loop composition (backend/app/discovery/loop.py):
  run_clear_d_loop classifies each generation's individuals by encoding
  and satisfiability, attributes UNSAT cores, produces offspring by rule
  (feasible -> random, infeasible -> conflict-directed), and selects with
  nsga2_select. nsga2.py unchanged.
- 18 tests (test_architecture_encoder.py, test_clear_d_loop.py).

### Fixed (Sprint 6 - PR #42)
- HierarchicalModel.check() no longer reports z3.unknown as unsat. The
  rollup is a pure function _rollup_status with explicit rules: unsat
  wins; unknown propagates; otherwise sat. 17 tests covering all 15
  status combinations.

### Fixed (Sprint 6 - PR #41)
- UnsatCoreExtractor.check() now guarantees minimal cores. Sets
  z3 core.minimize = True and runs a deletion-based minimizer. The
  deletion pass is the guarantee; the flag is best-effort per Z3
  documentation. 4 tests.

### Added (Sprint 6 - PRs #35..#40)
- Bayesian recursive update, vector Kalman update, numeric sensitivity
  (refinement/bayes.py).
- Adaptive PWL refinement (refinement/pwl_tune.py).
- Digital Twin discrepancy tracking (refinement/discrepancy.py).
- Stage E causal data-flow audit (refinement/causality.py).
- Notebook 08 closed-loop refinement convergence with corrected Kalman
  linearization (notebooks/08_closed_loop_refinement.ipynb).

### Added (Sprint 5 - PRs #22..#26)
- Tier 1 interpretable decision core with trace-as-byproduct-of-evaluation
  (control/tier1.py).
- Tier 2 atmospheric and trajectory surrogates with split-conformal
  calibration (control/tier2.py, control/trajectory.py).
- Static analyzer enforcing the two-tier invariant via AST call-graph BFS
  (control/static_analyzer.py).
- Explanation generator with rule-ablation counterfactuals
  (control/explain.py).
- Notebook 07 explanation-fidelity test.

### Added (Sprint 4 - PRs #18..#21)
- Architecture grammar with the Section 35.1 terminal set
  (discovery/grammar.py).
- Random candidate generation with at-least-one-source and
  at-least-one-UAV guarantees (discovery/generator.py).
- UNSAT-core extraction and minimality verifications
  (discovery/unsat.py).
- UNSAT-core-to-grammar-feature attribution — the defensively published
  inventive core (discovery/attribution.py).
- Eight mutation operators including conflict-directed mutation weighted
  by ConflictProneTable hit counts (discovery/mutation.py).
- NSGA-II Pareto selection over (C, R, E, N, T, U) with U minimized
  (discovery/nsga2.py).
- Notebook 06 unsat-core feedback ablation.

### Added (Sprint 3 - PRs #12..#17)
- PWL approximation builder with tracked epsilon (verification/pwl.py).
- Incremental Linearization encoding to SMT-LIB, Z3 only, no Lean
  (verification/encoder.py).
- Hierarchical decomposition with sound composition rule
  (verification/hierarchical.py).
- ANSI Z136.1 laser MPE and FCC Part 1.1310 RF constraint encoding
  (verification/regulatory.py).
- Notebooks 04 and 05.

### Documented (Sprint 3)
- Section 34.2 encoding-direction discrepancy. Under f_hat <= f, UNSAT is
  definitive and SAT may be a false positive. The spec's stronger claim
  ("SAT never falsely declares infeasible feasible") does not follow.
  Documented in pwl.py, encoder.py, and test_fuzz_soundness.py rather
  than silently resolved.
- s3-7 hierarchical scaling gate reformulation after measurement showed
  hierarchical is 10-20% slower than monolithic on structurally
  independent cluster constraints.


### Added (Sprint 2b - PR #9)
- Two-node lumped thermal model (backend/app/physics/thermal.py):
  PLC and TE nodes, Sb2Se3 barrier conduction, convective and radiative
  losses, steady-state solver, thermal-runaway boundary, and RK45
  forward integration.
- 27 tests for the thermal model (backend/tests/test_thermal.py).

### Changed (Sprint 2b - PR #9)
- eta_te now returns 0.0 for t_hot <= t_cold instead of raising.
  The strictly-colder branch is transiently reachable inside an
  adaptive ODE integrator, where a raise aborts the solver.
- backend/pyproject.toml: added [[tool.mypy.overrides]] for scipy.*
  so strict mypy accepts the conda-forge scipy install.

### Added (Sprint 2a - PR #8)
- Stage A receiver stack (backend/app/physics/receiver.py): PLC
  efficiency model, TE efficiency model, and the corrected Sb2Se3
  attribution (thermal barrier, not Seebeck layer).

### Added (Sprint 1 - PRs #4, #5, #6, #7)
- Skyfield SGP4/SDP4 orbital propagation (backend/app/physics/orbital.py).
- Visibility windows, cylindrical and conical eclipse detection, and
  topocentric look angles.
- Geographic region model with grid-based coverage (backend/app/physics/region.py).
- Notebook 02: LEO vs. GEO visibility comparison.
- CLA enforcement workflow.

### Added (Sprint 0 - PRs #1, #2, #3, #7)
- Backend FastAPI scaffold with /health and /metrics endpoints.
- Frontend scaffold (React 19.2, Vite 8.3, TypeScript 6.0, Vitest 4).
- Cascaded link-budget model with the dual-efficiency reporting
  invariant (backend/app/physics/link_budget.py).
- TRL-tagged benchmark table (backend/app/physics/benchmarks.py).
- Notebook 01: TRL benchmark validation (PowerLight, Xidian).
- CI pipeline: backend, frontend, formal-verification, cla-check.

## [0.1.0] - 2026-10-02

### Added
- Initial monorepo structure.
- Miniforge-based environment specification (environment.yml).
- FastAPI backend skeleton with /health endpoint.
- CI workflow (GitHub Actions).
- Formal verification toolchain: Z3.
