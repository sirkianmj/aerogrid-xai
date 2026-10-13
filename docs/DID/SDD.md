# Software Design Description — AeroGrid-XAI

| Field | Value |
|---|---|
| Document identifier | AGRID-SDD-001 |
| Version | 1.0 |
| Date | 2026-10-14 |
| Status | Baseline |
| Author | Kian Mansouri Jamshidi |
| Companion SRS | `docs/DID/SRS.md` (AGRID-SRS-001) |
| Structure | Follows the DI-IPSC-81433 SDD section layout (see SRS §1 note) |
| Repository state | `main` at commit `ea2141d` |

## 1. Scope

This SDD describes the architectural design of AeroGrid-XAI as
implemented at `ea2141d`. It is a *as-built* design document: every
component named here exists in the repository, and every design
element has a code path. It is not a forward-looking design.

The document is organized by architectural layer, then by component,
then by the requirement it satisfies. The forward-and-backward
traceability matrix is in §9.

## 2. Architectural overview

### 2.1 Layered structure

AeroGrid-XAI is a monorepo with three top-level layers:

    backend/        FastAPI application; all scientific code
    frontend/       React 19 / Vite / TypeScript SPA
    notebooks/      Jupyter notebooks (built by scripts/build_notebook_NN.py)

Supporting directories:

    docs/           specifications, audits, DID documents
    scripts/        notebook builders and native service scripts
    tests/          master_test.py (cross-layer harness)
    .github/        CI workflows

### 2.2 Backend subpackages

    backend/app/physics/        physical models (orbital, atmosphere,
                                beam, receiver, thermal, link_budget,
                                rectenna, region, geometry, catalog,
                                benchmarks, api)
    backend/app/verification/   PWL encoder, hierarchical decomposition,
                                regulatory constraints, architecture
                                encoder, api
    backend/app/discovery/      CLEAR-D stages C: grammar, generator,
                                unsat-core extraction, attribution,
                                mutation, NSGA-II, loop
    backend/app/control/        CLEAR-D stage D: tier1 (interpretable),
                                tier2 (surrogates), explain, trajectory,
                                static_analyzer, api
    backend/app/refinement/     CLEAR-D stage E: bayes, pwl_tune,
                                discrepancy, causality
    backend/app/saas/           multi-tenant SaaS: db, auth, billing,
                                billing_routes, idempotency, quota,
                                admin_routes, models, migrations
    backend/app/telemetry/      WebSocket telemetry
    backend/app/digital_twin/   twin state, trajectory, discrepancy
    backend/app/tradespace/     NSGA-II trade-space endpoint

### 2.3 CLEAR-D stage-to-component mapping

| Stage | Function | Backend component |
|---|---|---|
| A | Coupled electro-thermal physics → constraint functions | `physics/receiver.py`, `physics/thermal.py`, `physics/atmosphere.py`, `physics/beam.py`, `physics/link_budget.py` |
| B | PWL-SMT encoding with tracked ε | `verification/pwl.py`, `verification/encoder.py`, `verification/architecture_encoder.py`, `verification/hierarchical.py`, `verification/regulatory.py` |
| C | Generative discovery with UNSAT-core feedback | `discovery/grammar.py`, `generator.py`, `unsat.py`, `attribution.py`, `mutation.py`, `nsga2.py`, `loop.py` |
| D | Two-tier explanation-fidelity-preserving control | `control/tier1.py`, `tier2.py`, `explain.py`, `trajectory.py`, `static_analyzer.py` |
| E | Closed-loop refinement | `refinement/bayes.py`, `pwl_tune.py`, `discrepancy.py`, `causality.py` |

## 3. Component design

Each subsection names a design element, its inputs/outputs, its public
API, and the requirements it satisfies.

### 3.1 Physics: receiver efficiency

**Design element:** `ReceiverStack` (frozen dataclass) composes
`PLCParams`, `ThermalBarrierParams`, `TEParams`. The three-layer
attribution (CsPbBr₃ photovoltaic / Sb₂Se₃ thermal barrier / Bi₂Te₃
thermoelectric) is fixed by the dataclass shape: the barrier parameters
are consumed only by the thermal model, never by the `eta_te`
efficiency function.

**Public API:**
- `eta_plc(t_plc_k, params=None) -> float`
- `eta_te(t_hot_k, t_cold_k, params=None) -> float`
- `eta_total(t_plc_k, t_te_hot_k, t_te_cold_k, stack=None) -> float`
- `ReceiverStack.default() -> ReceiverStack`

**Rationale.** The multiplicative form `eta_PLC · eta_TE` is a first-order
lumped approximation, labeled as such in the docstring per specification
§33.2. Real PV-TE tandem power extraction depends on circuit topology
and is not rigorously derivable as a simple product.

**Satisfies:** SRS-FUN-030, SRS-FUN-031.

### 3.2 Physics: thermal model

**Design element:** `ThermalModel` implements a two-node lumped model
representing the PLC layer (node 1) and the TE layer (node 2). The
`Sb₂Se₃` thermal barrier enters the model as a conduction resistance
between the nodes, per specification §33.1.

**Public API:**
- `ThermalModel(params=None)` — constructor validating all parameters
- `capacitance_plc_j_per_k`, `capacitance_te_j_per_k`,
  `barrier_resistance_k_per_w`, `convection_coefficient_w_per_m2_k(v)`,
  `heat_absorbed_plc_w(p_incident_w, t_plc_k)`
- `steady_state(...)`, thermal-runaway boundary computation

**Satisfies:** SRS-FUN-032, SRS-FUN-033.

### 3.3 Physics: atmosphere

**Design element:** Beer-Lambert transmittance with a wavelength-dependent
extinction coefficient built from the Kruse three-branch aerosol model
and the Kim low-visibility refinement.

**Public API:**
- `transmission(wavelength_nm, path_length_m, visibility_km, cloud_factor, config=None) -> float`
- `AtmosphereConfig` frozen dataclass with the wavelength and visibility
  validity ranges documented in its docstring

**Rationale.** MODTRAN/HITRAN are reserved for offline calibration only
(specification §9.2). The runtime uses the parametrized Kruse-Kim model
which is fast enough for the discrete-event simulation loop.

**Satisfies:** SRS-FUN-020, SRS-FUN-021, SRS-FUN-022.

### 3.4 Physics: link budget

**Design element:** `LinkBudget` (frozen dataclass) with a tuple of
`Stage` factors. Two constructors:
- `build_canonical_link_budget(input_power_w, transmitter_eff, beam_eff, receiver_eff, battery_eff)`
  enforces the four-stage cascade order (transmitter → beam → receiver
  → battery) with caller-supplied efficiencies.
- `build_physical_link_budget(...)` derives the beam stage from Gaussian
  geometry (`beam.beam_radius_m`, `beam.combined_beam_efficiency`) and
  from atmospheric transmittance (`atmosphere.transmission`), with the
  remaining three stages caller-supplied.

`DualEfficiencyReport` enforces the specification §6 invariant that the
favorable and unfavorable figures must always be reported together:
the constructor refuses to build a report where the favorable value is
below the unfavorable value, and the shipped `XIDIAN_DUAL_REPORT` carries
both figures.

**Satisfies:** SRS-FUN-011, SRS-FUN-012, SRS-FUN-013.

### 3.5 Verification: PWL encoder

**Design element:** `PWLApproximation` is a piecewise-constant
over-approximation of a continuous function over a closed interval.
Each segment's constant value is set to the minimum sampled value of
the true function over that segment, so `f̂(x) ≤ f(x)` everywhere by
construction. The maximum gap `ε = max over segments of (max − min)` is
carried on the approximation.

**Public API:**
- `PWLSegment(x_lo, x_hi, slope, intercept)`
- `PWLApproximation(family_name, segments, epsilon, x_min, x_max)`
- `pwl_approximate(f, x_range, n_segments) -> PWLApproximation`

**Rationale.** Sound over-approximation: any x satisfying a constraint
on `f̂` satisfies it on `f`. This makes SAT verdicts conservative
(specification §34.2).

**Satisfies:** SRS-FUN-060, SRS-FUN-061.

### 3.6 Verification: architecture encoder

**Design element:** `encode_architecture(arch, config=None) ->
tuple[FeatureConstraint, ...]`. Emits five constraint families:

1. Per-link flow bounds: `0 ≤ flow ≤ base_capacity · capacity_factor`.
2. Per-source supply caps: `Σ outgoing flow ≤ source power_w`.
3. Per-UAV demand floors: `Σ incoming flow ≥ NODE_DEFAULT_DEMAND_W`. A
   UAV with no incoming link emits constant FALSE so the UNSAT core is
   a singleton naming that UAV.
4. Per-link regulatory MPE limits: laser per ANSI Z136.1, RF per FCC
   Part 1.1310, gated by `EncoderConfig.human_accessible_kinds`
   (default `{Ground_Station}`).
5. Structural `requires_uav`: fires constant FALSE when the architecture
   has no UAV node.

Every constraint carries the grammar features of its originating node
or link, so UNSAT cores attribute cleanly through
`attribution.attribute_and_mark`.

**Satisfies:** SRS-FUN-064, SRS-SAF-001 through SRS-SAF-004.

### 3.7 Discovery: attribution (the inventive core)

**Design element:** `attribute_and_mark(constraints, table) ->
AttributionResult`. When the constraint set is UNSAT, extracts the
minimal unsat core via Z3, maps each clause back to the `FeatureConstraint`
that emitted it, and marks every grammar feature carried by that
constraint as conflict-prone in the `ConflictProneTable`.

`ConflictProneTable` is a mutable accumulator keyed by `GrammarFeature`
(node type, link type, link instance). `mutate_conflict_directed`
samples mutation operators weighted by the table.

**Rationale.** This is the sole claimed novel feature (specification
§35.3, §40.3, §41). See `docs/DEFENSIVE_PUBLICATION.md` §2.1.

**Satisfies:** SRS-FUN-042, SRS-FUN-043, SRS-FUN-044.

### 3.8 Discovery: CLEAR-D loop

**Design element:** `run_clear_d_loop(initial_population, encoder,
evaluator, config, rng) -> ClearDLoopResult`. Per generation:

1. Classify every individual via `_classify` (encode → check → attribute).
2. Generate offspring: feasible individuals receive random mutation;
   infeasible individuals receive conflict-directed mutation weighted by
   the accumulated `ConflictProneTable`.
3. Select the next generation via `_constrained_select` (constrained
   domination: feasible always dominates infeasible).
4. Record per-generation statistics and hypervolume.

Each individual is classified exactly once. Feasibility of the surviving
population is derived from the combined parent-and-offspring pool, not
from re-classification.

**Satisfies:** SRS-FUN-045, SRS-FUN-046, SRS-FUN-047.

### 3.9 Control: Tier 1 interpretable core

**Design element:** `SparseRuleList.score_and_trace(inputs, builder) -> float`.
Evaluates every rule against the input mapping and records one
`TraceStep` per rule on the shared `TraceBuilder`. There is no code
path that produces a score without also recording the trace steps that
produced it. `DecisionTrace` and `TraceStep` are frozen dataclasses.

**Rationale.** Fidelity is a property of the API shape, not of a test
(see `docs/XAI_FIDELITY_AUDIT.md` §4). A future change that added a
second evaluation method returning a score without touching the builder
would break the invariant; the sweep test in
`test_xai_fidelity_audit.py::test_score_equals_sum_of_weights_across_sweep`
would catch it.

**Satisfies:** SRS-FUN-050, SRS-FUN-053, SRS-FUN-054.

### 3.10 Control: Tier 2 surrogates

**Design element:** `AtmosphericSurrogate` wraps a conformal-prediction
calibration (`calibrate(calibration_inputs, calibration_targets,
nominal_coverage)`) and exposes `estimate_atmospheric_loss(inputs) ->
Tier2Estimate`. `Tier2Estimate` is a frozen dataclass carrying
`(value, interval, model_name)`; there is no `action` field.

**Rationale.** Section 15.3 fixes the naming convention: Tier 2 functions
are `estimate_*`; Tier 1 functions are `decide_*`. The static analyzer
relies on this naming to verify the separation.

**Satisfies:** SRS-FUN-051.

### 3.11 Control: static analyzer

**Design element:** `analyze_default_package() -> list[Violation]`. Parses
every `.py` file under `app/control/`, builds a call graph keyed by
top-level function name, and reports every `estimate_*` function whose
transitive closure contains a `decide_*` function. The check is
transitive (BFS, not name lookup).

**Documented limitation.** Method calls (`obj.method(...)`) are not
tracked; only `ast.Call` nodes with a bare `ast.Name` function are
considered. This is recorded in the module docstring and in
`docs/XAI_FIDELITY_AUDIT.md` finding F-4.

**Satisfies:** SRS-FUN-052.

### 3.12 Refinement: PWL refiner

**Design element:** `AdaptivePWLRefiner(f, x_range, initial_n_segments,
max_segments, samples_per_segment)`. Maintains a list of breakpoints and
a current `PWLApproximation`. `observe(x, y)` accumulates operational
observations; `refine_once()` splits the segment with the highest
observed residual; `run_cycles(observation_source, n_cycles)` iterates
observe → refine → record.

**Rationale.** Splitting the highest-residual segment is the specific
mechanism that makes ε monotonically non-increasing at fixed `f`. This
is the theoretical basis of hypothesis H12 (specification §37.2).

**Satisfies:** SRS-FUN-072.

### 3.13 SaaS: database layer

**Design element:** `db.py` exposes `tenant_session(tenant_id)` and
`admin_session()`. `tenant_session` issues `SET LOCAL ROLE aerogrid_app`
followed by `SELECT set_config('app.tenant_id', :tid, true)` inside the
session's transaction. The superuser `aerogrid` bypasses RLS
unconditionally, so the role switch is what makes the RLS policy active.
`admin_session` is the superuser session and is explicitly marked for
cross-tenant administrative work only.

**Satisfies:** SRS-FUN-080, SRS-FUN-081, SRS-SEC-002.

### 3.14 SaaS: auth

**Design element:** `issue_token(tenant_id, role, ttl_seconds=86400)`,
`decode_token(token) -> TenantContext`, `require_tenant(request) ->
TenantContext`, `require_role(minimum) -> Callable[[Request], TenantContext]`.
HS256 JWTs. Roles are ordered: viewer < admin < superadmin. The signing
secret comes from `AEROGRID_JWT_SECRET`; the development default is used
only when `AEROGRID_ENV=development`.

**Satisfies:** SRS-FUN-082, SRS-SEC-001.

### 3.15 SaaS: quota

**Design element:** `consume(store, tenant_id, plan, metric, now=None) ->
int`. Atomically increments a counter keyed by `(tenant_id, metric,
period_start)`; raises HTTP 429 with `Retry-After` if the new count
exceeds the plan limit. The `now` parameter is the reference time for
both the period computation and the `Retry-After` header. The increment
happens before the limit check, so an over-limit attempt is charged.

`QuotaStore` is a runtime-checkable protocol; `PostgresQuotaStore`
implementsthe production path; `FakeQuotaStore` is the in-memory double.

**Satisfies:** SRS-FUN-083.

### 3.16 Frontend: feature module structure

**Design element:** each feature lives under `frontend/src/features/<Name>/`
with a `<Name>.tsx` component, a `<Name>Api.ts` typed client, and a
`<Name>.test.tsx` test module. Every panel wraps its output in
`TaggedOutput` so the epistemic tag is structurally required rather
than conventional.

**Satisfies:** SRS-FUN-090, SRS-FUN-092, SRS-FUN-093.

## 4. Data design

### 4.1 Persistent stores

| Store | Schema | Migration |
|---|---|---|
| PostgreSQL `tenants` | id, slug, display_name, created_at, three nullable Stripe columns | `001`, `002` |
| PostgreSQL `missions` | id, tenant_id, name, created_at (RLS on tenant_id) | `001` |
| PostgreSQL `quota_usage` | tenant_id, metric, period_start, count (RLS on tenant_id) | `003` |
| PostgreSQL `stripe_events` | event_id, event_type, received_at | `002` |
| Redis | session cache and rate-limit tokens | n/a |
| MinIO | tenant-scoped object storage | n/a |

### 4.2 Non-persistent state

`ConflictProneTable` and `TraceBuilder` are in-memory and per-run. Neither
is serialized except as part of a notebook's executed output.

## 5. Interface design

### 5.1 HTTP API

Routers registered in `backend/app/main.py`:

| Prefix | Router | Purpose |
|---|---|---|
| `/health`, `/metrics` | `main.py` | Liveness, Prometheus |
| (none) | `control.api` | `POST /decisions/charge` |
| `/physics` | `physics.api` | Physics models |
| `/orbital` | `physics.api` | Satellite tracking, visibility |
| `/digital-twin` | `digital_twin.api` | State, trajectory, discrepancy |
| `/tradespace` | `tradespace.api` | NSGA-II Pareto front |
| `/saas` | `saas.routes` | whoami, mission-count |
| `/saas` | `saas.billing_routes` | checkout-session, subscription, webhook |
| `/saas/admin` | `saas.admin_routes` | tenants list, tenant usage |
| `/telemetry` (WS) | `telemetry.api` | Streaming telemetry |

### 5.2 CLI entry points

- `python tests/master_test.py [--backend|--frontend|--notebooks] [--require-db]`
- `python scripts/build_notebook_NN.py`
- `python -m app.control.static_analyzer`
- `make test`, `make lint`, `make format`, `make master-test`, `make master-test-ci`

## 6. Design decisions and rationale

| Decision | Rationale | Reference |
|---|---|---|
| No Docker, no K8s, no cloud | D2 | `docs/ROADMAP_STATUS.md` |
| Z3 only (no Lean) | D5 | same |
| Single conda env `aerogrid` | D10 | same |
| Backend under `backend/app/` | D8 | same |
| Top-level `infrastructure/` empty until Sprint 11 | D2/D9 | same |
| Defensive publication not patent | D1 | `docs/DEFENSIVE_PUBLICATION.md` |
| Tier 1 restricted to interpretable models | §15.3 | `docs/XAI_FIDELITY_AUDIT.md` |
| Sound PWL over-approximation | §34.2 | `docs/ENCODER_PHYSICS_INTEGRATION.md` |
| Attribution maps UNSAT clauses to grammar features | §35.3 | `docs/DEFENSIVE_PUBLICATION.md` §2.1 |

## 7. Constraints

- **Python 3.12** (D10).
- **macOS host** for local development (D2).
- **Z3 5.1.x** is the only formal-verification backend (D5).
- **No physical hardware** is modeled as a deliverable; the platform is
  software and simulation only.
- **Single maintainer.** Every contributor must be recorded in
  `signatures/cla-v1.json` before `cla-check` will pass.

## 8. Design limitations

- `static_analyzer` does not cover method calls (`obj.method(...)`),
  documented as F-4.
- `TraceStep.observed` does not record per-value provenance (which input
  mapping supplied a value), documented as F-3.
- The `eta_plc` model has a hard material discontinuity at `T_MAX_K =
  358.45 K`; the PWL domain is restricted to the pre-cutoff band, per
  Notebook 10 F-1.
- The generator does not verify combined UAV supply versus demand; the
  encoder's `demand_unmet` family catches the case as UNSAT.
- `generator.encode_architecture_to_z3` is a placeholder superseded by
  `verification.architecture_encoder.encode_architecture`; it is still
  present in the tree and marked SUPERSEDED in its docstring.

## 9. Traceability matrix (SRS → SDD)

| SRS ID | SDD design element | Verifying test |
|---|---|---|
| SRS-FUN-001 | §3.1 orbital propagation | `test_orbital.py`, `test_sgp4_reference.py` |
| SRS-FUN-002 | §3.1 visibility | `test_visibility.py` |
| SRS-FUN-003 | §3.1 eclipse | `test_eclipse_conical.py` |
| SRS-FUN-004 | §3.1 region | `test_region.py` |
| SRS-FUN-005 | §3.1 no-hardcoded-positions | `test_no_hardcoded_positions.py` |
| SRS-FUN-010 | §3.4 link budget (all modalities) | `test_beam_and_physical_link_budget.py` |
| SRS-FUN-011 | §3.4 cascaded link budget | `test_link_budget.py` |
| SRS-FUN-012 | §3.4 dual-report invariant | `test_link_budget_gate.py` |
| SRS-FUN-013 | §3.4 stage product | `test_link_budget.py` |
| SRS-FUN-020 | §3.3 atmosphere | `test_atmosphere.py` |
| SRS-FUN-021 | §3.3 Kruse-Kim | `test_atmosphere.py` |
| SRS-FUN-022 | §3.10 Tier2 uncertainty | `test_tier2.py` |
| SRS-FUN-030 | §3.1 three-layer attribution | `test_receiver.py`, `test_thermal.py` |
| SRS-FUN-031 | §3.1 monotonic efficiency | `test_receiver.py` |
| SRS-FUN-032 | §3.2 two-node thermal | `test_thermal.py` |
| SRS-FUN-033 | §3.2 runaway boundary | `test_thermal.py` |
| SRS-FUN-040 | §3.7 grammar | `test_grammar.py` |
| SRS-FUN-041 | §3.6 generator → encoder | `test_generator.py`, `test_generator_los.py` |
| SRS-FUN-042 | §3.7 unsat core | `test_unsat.py` |
| SRS-FUN-043 | §3.7 attribution | `test_attribution.py` |
| SRS-FUN-044 | §3.7 conflict-directed mutation | `test_h9_convergence.py`, `test_mutation.py` |
| SRS-FUN-045 | §3.8 CLEAR-D loop | `test_z3_end_to_end.py` |
| SRS-FUN-046 | §3.8 NSGA-II selection | `test_nsga2.py` |
| SRS-FUN-047 | §3.8 determinism | `test_discovery_determinism.py` |
| SRS-FUN-050 | §3.9 Tier 1 classes | `tier1.py` inspection + `docs/XAI_FIDELITY_AUDIT.md` |
| SRS-FUN-051 | §3.10 Tier 2 API | `test_tier2.py` |
| SRS-FUN-052 | §3.11 static analyzer | `test_static_analyzer.py` |
| SRS-FUN-053 | §3.9 trace fidelity | `test_tier1.py`, `test_xai_fidelity_audit.py` |
| SRS-FUN-054 | §3.9 counterfactuals | `test_explain.py` |
| SRS-FUN-060 | §3.5 PWL soundness | `test_pwl.py` |
| SRS-FUN-061 | §3.5 ε tracking | `test_pwl.py`, `test_pwl_tune.py` |
| SRS-FUN-062 | §3.5 conservative SAT | `test_fuzz_soundness.py` |
| SRS-FUN-063 | §3.6 hierarchical decomposition | `test_hierarchical.py` |
| SRS-FUN-064 | §3.6 regulatory | `test_regulatory.py` |
| SRS-FUN-070 | §3.12 Bayesian update | `test_bayes.py` |
| SRS-FUN-071 | §3.12 posterior variance | `test_bayes.py` |
| SRS-FUN-072 | §3.12 H12 epsilon reduction | `test_pwl_tune.py`, `notebooks/10_clear_d_end_to_end.ipynb` |
| SRS-FUN-073 | §3.12 discrepancy trigger | `test_discrepancy.py` |
| SRS-FUN-074 | §3.12 causality | `test_causality.py` |
| SRS-FUN-080 | §3.13 RLS | `test_rls_isolation.py` |
| SRS-FUN-081 | §3.13 tenant session | `test_rls_isolation.py` |
| SRS-FUN-082 | §3.14 auth | `test_saas_auth.py` |
| SRS-FUN-083 | §3.15 quota | `test_saas_quota.py` |
| SRS-FUN-084 | §3.15 admin RBAC | `test_saas_admin_routes.py` |
| SRS-FUN-090 | §3.16 epistemic tagging | `EpistemicBadge.test.tsx` |
| SRS-FUN-091 | §3.16 UI audit | PARTIAL (P34) |
| SRS-FUN-092 | §3.16 confidence scope text | `XAITrace.test.tsx` |
| SRS-FUN-093 | §3.16 WCAG AA | `contrast.test.ts` |
| SRS-PER-001 | §3.8 loop performance | `test_z3_end_to_end.py` |
| SRS-PER-002 | §3.16 telemetry | `Telemetry.test.tsx` |
| SRS-PER-003 | §3.6 hierarchical scaling | `notebooks/05_smt_scaling.ipynb` |
| SRS-PER-004 | §3.16 bundle size | `package.json` build |
| SRS-INT-001 | §5.1 health | `test_health.py` |
| SRS-INT-002 | §5.1 metrics | `test_health.py` |
| SRS-INT-003 | §5.1 openapi | `test_tradespace_api.py` |
| SRS-INT-004 | §5.1 telemetry ws | `test_telemetry_ws.py` |
| SRS-SAF-001 | §3.6 laser MPE | `test_regulatory.py` |
| SRS-SAF-002 | §3.6 RF MPE | `test_regulatory.py` |
| SRS-SAF-003 | §3.6 human_accessible_kinds | `test_encoder_physics.py` |
| SRS-SAF-004 | §6 constants | `test_dimensional_consistency.py` |
| SRS-SEC-001 | §3.14 JWT secret | `test_saas_auth.py` |
| SRS-SEC-002 | §3.13 roles | `docs/ISOLATION_AUDIT.md` §4.3 |
| SRS-SEC-003 | §3.15 webhook HMAC | `test_saas_billing_routes.py` |
| SRS-VER-001 | §6 CLAIMS document | `docs/SCIENTIFIC_CLAIMS.md` |
| SRS-VER-002 | §6 CITATION_AUDIT document | `docs/CITATION_AUDIT.md` |
| SRS-VER-003 | §5.2 master_test.py | `tests/master_test.py` |
| SRS-VER-004 | §3.13 ISOLATION_AUDIT document | `docs/ISOLATION_AUDIT.md` |
| SRS-VER-005 | §5.2 notebook-repro.yml | `.github/workflows/notebook-repro.yml` |

Signed: Kian Mansouri Jamshidi
