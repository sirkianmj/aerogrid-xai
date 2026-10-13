# Software Requirements Specification — AeroGrid-XAI

| Field | Value |
|---|---|
| Document identifier | AGRID-SRS-001 |
| Version | 1.0 |
| Date | 2026-10-14 |
| Status | Baseline |
| Author | Kian Mansouri Jamshidi |
| Source specification | *AeroGrid-XAI Final Comprehensive Specification (Rev. 6)* |
| Repository state | `main` at commit `ea2141d` |
| Structure | Follows the DI-IPSC-81428 SRS section layout (see §1 note) |

## Scope of this document

This SRS states the **system-level requirements** for AeroGrid-XAI, a research-grade software platform that models, simulates, formally verifies, and generatively discovers architectures for wireless energy transfer between space, air, and ground nodes.

It is a **research SRS**, not a government-contract deliverable. It is written to the DI-IPSC-81428 section structure so that the requirement set can be reviewed under a familiar framework, and so that every requirement can be traced forward to a design element (SDD) and to a verification method (STR). Where the DID template presumes a contractually defined deliverable with a customer and acceptance authority, this document states the research-context equivalent explicitly rather than leaving the field blank.

The AeroGrid-XAI platform does not claim any physical hardware. Requirements that would be satisfied by hardware are explicitly out of scope (see §6).

**Standard-number note.** The DID standard numbers cited in this document (DI-IPSC-81428 for the SRS section layout, DI-IPSC-81433 for the SDD, DI-IPSC-81434 for the STR) are recorded as the identifiers of the respective DID templates. The roadmap names the pair `DI-IPSC-81428/81433` for this task. The exact current revision of each DID template was not cross-checked against a DoD source during preparation; that check is recorded in `docs/CITATION_AUDIT.md` as item **CIT-1**. The section structure the documents follow is the widely-published layout associated with those identifiers; the identifier-to-layout mapping is the assertion under audit.

## 1. Applicable documents

| Ref | Document | Role |
|---|---|---|
| SPEC | *AeroGrid-XAI Final Comprehensive Specification (Rev. 6)* | Normative source of every requirement below |
| ROAD | *AeroGrid-XAI Master Engineering Roadmap (Rev. 2)* | Sprint ledger; not normative for requirements |
| D1–D10 | Adopted engineering deviations (specified in ROAD) | Constraints on requirements that touch tooling, runtime, and layout |
| CLAIMS | `docs/SCIENTIFIC_CLAIMS.md` | Claims-to-test map; governs which claims are considered covered |
| CITES | `docs/CITATION_AUDIT.md` | External-reference classification; governs verifiability of cited values |
| DEFPUB | `docs/DEFENSIVE_PUBLICATION.md` | Prior-art record for the CLEAR-D method |
| ISO-25010 | ISO/IEC 25010:2011 quality model | Framework for the quality-attribute headings |

## 2. System overview

### 2.1 System function

AeroGrid-XAI provides a software-only environment in which candidate architectures for wireless energy transfer between satellites, UAVs, and ground stations can be represented, simulated, formally verified, and — via the CLEAR-D method — generatively discovered. CLEAR-D (Coupled-Loop Epistemic Architecture Reasoning and Discovery) is a five-stage closed loop whose stages are:

- **A** — Coupled electro-thermal physics constraint generation.
- **B** — PWL-SMT encoding with tracked approximation error ε.
- **C** — Generative architecture discovery with UNSAT-core feedback.
- **D** — Two-tier explanation-fidelity-preserving control.
- **E** — Closed-loop refinement of the physics model and the formal encoding.

### 2.2 Operating environment

- Host: macOS (Miniforge `aerogrid` conda environment; see D10).
- Backend: FastAPI (Python 3.12).
- Frontend: React 19 / Vite / TypeScript.
- Services: PostgreSQL 16, Redis 8, MinIO (all native; see D2, D3).
- Formal verification: Z3 5.1.x (see D5).
- No Docker, no Kubernetes, no cloud VMs (D2).

### 2.3 Users

| Class | Role |
|---|---|
| Researcher | Author and consumer of the specification; drives discovery runs. |
| Operator | Configures a mission; runs CLEAR-D; consumes the trace and the Pareto front. |
| Auditor | Reads the XAI trace, the isolation audit, the citation audit, and the scientific claims map. |
| Tenant (SaaS) | Enters via an authenticated JWT; consumes metered quota; cannot see other tenants. |

## 3. Requirements

Requirements are numbered `SRS-<family>-<n>`. Each carries:

- **Source**: the specification section that states it.
- **Priority**: M (mandatory), C (conditional), O (optional).
- **Verification method**: T (test), A (analysis), I (inspection), D (demonstration).
- **Verifying artifact**: the exact test module, notebook, or document that would fail if the requirement were violated.

If a requirement has no verifying artifact, it is marked **UNVERIFIED** and is invalid per the s9-7 rule (`docs/SCIENTIFIC_CLAIMS.md`).

### 3.1 Functional requirements

#### 3.1.1 Orbital and geographic modelling

| ID | Requirement | Source | Pri | Ver | Verifying artifact |
|----|-------------|--------|-----|-----|---------------------|
| SRS-FUN-001 | The system shall propagate a satellite's position and velocity as a function of time using SGP4/SDP4 from a TLE. | SPEC §7.1 | M | T | `backend/tests/test_orbital.py`, `test_sgp4_reference.py` |
| SRS-FUN-002 | The system shall compute visibility windows between a satellite and any ground or air node. | SPEC §7.1 | M | T | `backend/tests/test_visibility.py` |
| SRS-FUN-003 | The system shall compute eclipse periods as a function of time. | SPEC §7.1 | M | T | `backend/tests/test_eclipse_conical.py` |
| SRS-FUN-004 | The system shall represent geographic regions and compute grid-based coverage. | SPEC §11 | M | T | `backend/tests/test_region.py` |
| SRS-FUN-005 | No orbital state shall be hard-coded; all positions shall be time-varying via SGP4. | SPEC §7.1 | M | T | `backend/tests/test_no_hardcoded_positions.py` |

#### 3.1.2 Wireless power transmission

| ID | Requirement | Source | Pri | Ver | Verifying artifact |
|----|-------------|--------|-----|-----|---------------------|
| SRS-FUN-010 | The system shall model laser, microwave, and hybrid transmission modalities. | SPEC §8 | M | T | `backend/tests/test_beam_and_physical_link_budget.py`, `test_encoder_physics.py` |
| SRS-FUN-011 | The system shall compute a cascaded link budget in which each stage is tracked separately. | SPEC §8.4 | M | T | `backend/tests/test_link_budget.py`, `test_link_budget_gate.py` |
| SRS-FUN-012 | The link-budget model shall report the Xidian favorable (20.8%) and unfavorable (3–5%) figures together, never one alone. | SPEC §6, §8.4 | M | T | `backend/tests/test_link_budget_gate.py::test_xidian_dual_report_both_figures_present`, `backend/tests/scientific_validation/test_xidian.py` |
| SRS-FUN-013 | The end-to-end efficiency shall equal the product of the individual stage efficiencies, with no collapsed single number permitted. | SPEC §8.4 | M | T | `backend/tests/test_link_budget.py::test_end_to_end_efficiency_is_product_of_stages` |

#### 3.1.3 Atmospheric modelling

| ID | Requirement | Source | Pri | Ver | Verifying artifact |
|----|-------------|--------|-----|-----|---------------------|
| SRS-FUN-020 | The system shall model atmospheric transmittance using the Beer–Lambert law. | SPEC §9.3 | M | T | `backend/tests/test_atmosphere.py` |
| SRS-FUN-021 | The system shall model aerosol extinction using the Kruse three-branch form with the Kim low-visibility refinement. | SPEC §9.2 | M | T | `backend/tests/test_atmosphere.py` |
| SRS-FUN-022 | Atmospheric-loss estimates shall carry a calibrated uncertainty interval. | SPEC §17 | M | T | `backend/tests/test_tier2.py::test_gate_90pct_coverage_at_least_85pct` |

#### 3.1.4 Receiver and thermal modelling

| ID | Requirement | Source | Pri | Ver | Verifying artifact |
|----|-------------|--------|-----|-----|---------------------|
| SRS-FUN-030 | The three-layer receiver stack shall attribute each layer correctly: CsPbBr₃ photovoltaic; Sb₂Se₃ thermal barrier; Bi₂Te₃ thermoelectric. Sb₂Se₃ shall not appear in the TE efficiency product. | SPEC §33.1 | M | T | `backend/tests/test_receiver.py`, `test_thermal.py` |
| SRS-FUN-031 | Receiver efficiency shall decrease monotonically with PLC temperature over the operating range. | SPEC §33.2 | M | T | `backend/tests/test_receiver.py` |
| SRS-FUN-032 | The two-node lumped thermal model shall close the energy balance and match the reported 80–90 °C steady-state regime. | SPEC §33.3 | M | T | `backend/tests/test_thermal.py` |
| SRS-FUN-033 | The system shall compute a thermal-runaway boundary P_max(T_amb, v). | SPEC §33.4 | M | T | `backend/tests/test_thermal.py` |

#### 3.1.5 CLEAR-D discovery method

| ID | Requirement | Source | Pri | Ver | Verifying artifact |
|----|-------------|--------|-----|-----|---------------------|
| SRS-FUN-040 | The system shall represent the architecture space as a context-free grammar with node and link terminals. | SPEC §35.1 | M | T | `backend/tests/test_grammar.py` |
| SRS-FUN-041 | The generator shall produce candidate architectures that encode to Z3 without error. | SPEC §35.1, §5.6 | M | T | `backend/tests/test_generator.py`, `test_generator_los.py` |
| SRS-FUN-042 | When a candidate architecture is UNSAT, the system shall extract a minimal unsat core. | SPEC §35.3 | M | T | `backend/tests/test_unsat.py` |
| SRS-FUN-043 | The system shall map each clause of the unsat core to the grammar production rule that generated it, and mark that feature as conflict-prone. | SPEC §35.3 | M | T | `backend/tests/test_attribution.py` |
| SRS-FUN-044 | Conflict-directed mutation shall bias subsequent candidates away from conflict-prone features. | SPEC §35.3 | M | T | `backend/tests/test_h9_convergence.py`, `test_mutation.py` |
| SRS-FUN-045 | The CLEAR-D loop shall complete 100 generations over the real Stage B encoder without error. | SPEC §35.4 | M | T | `backend/tests/test_z3_end_to_end.py::test_100_generations_completes_without_error` |
| SRS-FUN-046 | The Pareto-based multi-objective optimization (NSGA-II) shall produce a non-dominated front over the (C, R, E, N, T, U) vector. | SPEC §14 | M | T | `backend/tests/test_nsga2.py` |
| SRS-FUN-047 | The system shall be deterministic given a fixed seed for the discovery loop. | SPEC §35.4 | M | T | `backend/tests/test_discovery_determinism.py`, `test_z3_end_to_end.py::test_100_generations_is_deterministic_under_fixed_seed` |

#### 3.1.6 Two-tier XAI controller

| ID | Requirement | Source | Pri | Ver | Verifying artifact |
|----|-------------|--------|-----|-----|---------------------|
| SRS-FUN-050 | Tier 1 shall be restricted to model classes whose explanation is their computation (sparse rule lists, GAMs, bounded trees, transparent MPC). | SPEC §15.3 | M | I | `backend/app/control/tier1.py` (module docstring and API); `docs/XAI_FIDELITY_AUDIT.md` §4 |
| SRS-FUN-051 | Tier 2 shall expose only `estimate_*` functions of the form `(value, uncertainty_interval)`. | SPEC §15.3 | M | T | `backend/tests/test_tier2.py::test_surrogate_estimate_is_deterministic`; `test_xai_fidelity_audit.py::test_tier2_estimates_are_value_and_interval_only` |
| SRS-FUN-052 | Tier 2 shall never reach the Tier 1 action interface, enforced by a transitive call-graph check at build time. | SPEC §36.1 | M | T | `backend/tests/test_static_analyzer.py::test_real_control_package_is_clean` |
| SRS-FUN-053 | Every Tier 1 decision shall carry a trace that is, by construction, the literal computation path used to reach the decision. | SPEC §15.3 | M | T | `backend/tests/test_tier1.py::test_trace_score_equals_sum_of_step_weights`; `test_xai_fidelity_audit.py::test_score_equals_sum_of_weights_across_sweep` |
| SRS-FUN-054 | Counterfactual explanations shall be exact statements about the Tier 1 rule structure. | SPEC §26 | M | T | `backend/tests/test_explain.py::test_counterfactual_ablating_decisive_rule_flips_decision` |

#### 3.1.7 Formal verification layer

| ID | Requirement | Source | Pri | Ver | Verifying artifact |
|----|-------------|--------|-----|-----|---------------------|
| SRS-FUN-060 | Every transcendental physics function used in a Z3 constraint shall be replaced by a piecewise-linear over-approximation (sound: f̂ ≤ f everywhere). | SPEC §20.2, §34.2 | M | T | `backend/tests/test_pwl.py` |
| SRS-FUN-061 | The maximum approximation error ε shall be carried as a numeric quantity and reported with every verification result. | SPEC §20.2 | M | T | `backend/tests/test_pwl.py`, `test_pwl_tune.py` |
| SRS-FUN-062 | A SAT verdict shall never falsely declare an infeasible architecture feasible (conservative direction). | SPEC §34.2 | M | T | `backend/tests/test_fuzz_soundness.py` |
| SRS-FUN-063 | Network-scale SMT queries shall be decomposed into intra-cluster problems and inter-cluster flow problems, with a documented sound composition rule. | SPEC §34.3 | M | T | `backend/tests/test_hierarchical.py` |
| SRS-FUN-064 | Regulatory constraints (ANSI Z136.1 laser MPE, FCC Part 1.1310 RF) shall be encoded as hard constraints; an MPE-violating architecture shall be UNSAT by construction. | SPEC §16, §20 | M | T | `backend/tests/test_regulatory.py` |

#### 3.1.8 Closed-loop refinement

| ID | Requirement | Source | Pri | Ver | Verifying artifact |
|----|-------------|--------|-----|-----|---------------------|
| SRS-FUN-070 | Physics parameters shall be refined via recursive Bayesian estimation against observations. | SPEC §37.1 | M | T | `backend/tests/test_bayes.py` |
| SRS-FUN-071 | Posterior variance shall strictly decrease under nonzero-sensitivity updates (theorem, not empirical claim). | SPEC §37.1 | M | T | `backend/tests/test_bayes.py::test_posterior_variance_strictly_less_than_prior` |
| SRS-FUN-072 | PWL approximation error ε shall reduce by at least 50% over 100 refinement cycles at fixed physics (hypothesis H12). | SPEC §39 (H12) | M | T | `backend/tests/test_pwl_tune.py::test_h12_epsilon_reduces_by_half_over_100_cycles`; `notebooks/10_clear_d_end_to_end.ipynb` (ratio 0.125) |
| SRS-FUN-073 | Digital Twin discrepancy tracking shall raise a trigger when observed-vs-predicted deviation exceeds a configured threshold. | SPEC §37.1 | M | T | `backend/tests/test_discrepancy.py` |
| SRS-FUN-074 | The Stage E data flow shall be causal: operational data affects the model, not the reverse. | SPEC §37.2 | M | T | `backend/tests/test_causality.py` |

#### 3.1.9 SaaS multi-tenant layer

| ID | Requirement | Source | Pri | Ver | Verifying artifact |
|----|-------------|--------|-----|-----|---------------------|
| SRS-FUN-080 | Tenant isolation shall be enforced by PostgreSQL row-level security, not by application-layer WHERE clauses. | SPEC §23 | M | T | `backend/tests/test_rls_isolation.py`; `docs/ISOLATION_AUDIT.md` |
| SRS-FUN-081 | Every tenant-scoped query shall run under the non-superuser role `aerogrid_app` with `SET LOCAL app.tenant_id` set. | SPEC §23 | M | T | `backend/tests/test_rls_isolation.py::test_app_role_with_unset_guc_sees_zero_rows` |
| SRS-FUN-082 | Tenant authentication shall use HS256 JWTs with claims `sub` (tenant UUID) and `role` (viewer/admin/superadmin). | SPEC §23 | M | T | `backend/tests/test_saas_auth.py` |
| SRS-FUN-083 | Quota consumption shall atomically increment a per-tenant, per-metric, per-period counter and reject over-limit calls with HTTP 429 and `Retry-After`. | SPEC §23 | M | T | `backend/tests/test_saas_quota.py` |
| SRS-FUN-084 | Admin endpoints shall require the superadmin role. | SPEC §23 | M | T | `backend/tests/test_saas_admin_routes.py` |

#### 3.1.10 Epistemic hierarchy and UI

| ID | Requirement | Source | Pri | Ver | Verifying artifact |
|----|-------------|--------|-----|-----|---------------------|
| SRS-FUN-090 | Every output artifact (chart, report, API response, decision explanation) shall be tagged with one of the seven Section 21 epistemic categories. | SPEC §21 | M | T + I | `frontend/src/components/EpistemicBadge/EpistemicBadge.test.tsx`; `docs/SCIENTIFIC_CLAIMS.md`; per-panel `TaggedOutput` usage |
| SRS-FUN-091 | The UI shall not present a simulation result, an AI prediction, or a formal verification result as if it were a physical measurement. | SPEC §21 | M | I | Audit pending — see `docs/ROADMAP_STATUS.md` P34; the tagging infrastructure exists but the enforcement audit is not yet complete. Marked **PARTIAL**. |
| SRS-FUN-092 | Where the word "confidence" or "fidelity" appears in the UI, the accompanying text shall state the scope (§15.5 limitation). | SPEC §15.5 | M | T | `frontend/src/features/XAITrace/XAITrace.test.tsx` |
| SRS-FUN-093 | NASA/ANSI style WCAG 2.1 AA contrast ratios (≥ 4.5:1 for body text) shall be enforced by test. | SPEC §21 (implicit via ROAD s7-1) | M | T | `frontend/src/lib/contrast.test.ts` |

### 3.2 Performance requirements

| ID | Requirement | Source | Pri | Ver | Verifying artifact |
|----|-------------|--------|-----|-----|---------------------|
| SRS-PER-001 | The discovery loop shall complete 100 generations of population 4 within a single test module's default timeout (< 300 s). | SPEC §35.4 | M | T | `backend/tests/test_z3_end_to_end.py` (isolation run: 0.23 s) |
| SRS-PER-002 | Telemetry WebSocket latency shall be bounded such that a ring buffer of at least 1000 samples is maintained. | SPEC §24 | M | T | `frontend/src/features/Telemetry/Telemetry.test.tsx` |
| SRS-PER-003 | The Z3 formal verification layer shall complete the hierarchical decomposition on a network of at least 50 nodes where monolithic encoding times out. | SPEC §34.3 | M | T | `notebooks/05_smt_scaling.ipynb` |
| SRS-PER-004 | The frontend production bundle shall build successfully; current size ~1.2 MB (330 KB gzipped) is a known limit (P31), documented as not blocking. | SPEC §24 | O | D | `frontend/package.json` build script; CI `frontend` job |

### 3.3 Interface requirements

| ID | Requirement | Source | Pri | Ver | Verifying artifact |
|----|-------------|--------|-----|-----|---------------------|
| SRS-INT-001 | The backend shall expose a `/health` endpoint returning `{"status": "healthy"}`. | SPEC §24 | M | T | `backend/tests/test_health.py` |
| SRS-INT-002 | The backend shall expose a Prometheus `/metrics` endpoint. | SPEC §24 | M | T | `backend/tests/test_health.py` (openapi path check) |
| SRS-INT-003 | Every HTTP route shall appear in `/openapi.json`. | SPEC §24 | M | T | `backend/tests/test_tradespace_api.py::test_openapi_lists_all_routers` |
| SRS-INT-004 | Telemetry shall be delivered over `WS /telemetry/stream`. | SPEC §24 | M | T | `backend/tests/test_telemetry_ws.py` |

### 3.4 Safety and regulatory requirements

| ID | Requirement | Source | Pri | Ver | Verifying artifact |
|----|-------------|--------|-----|-----|---------------------|
| SRS-SAF-001 | ANSI Z136.1 MPE limits at 1064 nm shall be encoded as hard constraints in the Z3 verification layer. | SPEC §16 | M | T | `backend/tests/test_regulatory.py` |
| SRS-SAF-002 | FCC Part 1.1310 RF limits shall be encoded as hard constraints. | SPEC §16 | M | T | `backend/tests/test_regulatory.py` |
| SRS-SAF-003 | MPE constraints shall apply only when the link target node kind is in `EncoderConfig.human_accessible_kinds` (default: `{Ground_Station}`). | SPEC §16 | M | T | `backend/tests/test_encoder_physics.py`, `test_architecture_encoder.py` |
| SRS-SAF-004 | Physical constants (Stefan-Boltzmann, T_REF_K, PLC t_max, MPE values) shall be sourced from named references and shall not change silently. | SPEC §33.5 | M | T + I | `backend/tests/test_dimensional_consistency.py`; `docs/CITATION_AUDIT.md` |

### 3.5 Security requirements

| ID | Requirement | Source | Pri | Ver | Verifying artifact |
|----|-------------|--------|-----|-----|---------------------|
| SRS-SEC-001 | JWT signing secret shall be read from `AEROGRID_JWT_SECRET`; a development default shall only be used when `AEROGRID_ENV=development`. | SPEC §23 | M | T | `backend/tests/test_saas_auth.py` |
| SRS-SEC-002 | The application role `aerogrid_app` shall have `NOSUPERUSER`, `NOBYPASSRLS`, and `NOLOGIN`. | SPEC §23 | M | T + I | `docs/ISOLATION_AUDIT.md` §4.3; migration `001_rls_setup.sql` |
| SRS-SEC-003 | Stripe webhook deliveries shall be verified by HMAC signature and deduplicated on event ID. | SPEC §23 | M | T | `backend/tests/test_saas_billing_routes.py` |

### 3.6 Verification and certification requirements

| ID | Requirement | Source | Pri | Ver | Verifying artifact |
|----|-------------|--------|-----|-----|---------------------|
| SRS-VER-001 | Every scientific claim in the specification shall appear in `docs/SCIENTIFIC_CLAIMS.md` with a status of COVERED, PARTIAL, or UNCOVERED; an UNCOVERED claim is invalid. | SPEC §27, §28; ROAD s9-7 | M | I | `docs/SCIENTIFIC_CLAIMS.md` |
| SRS-VER-002 | Every external citation shall appear in `docs/CITATION_AUDIT.md` with a status per well-formedness, existence, and value attribution. | ROAD s10-6 | M | I | `docs/CITATION_AUDIT.md` |
| SRS-VER-003 | The master test harness shall fail if any enabled phase (backend, frontend, notebooks) reports a non-PASS. | ROAD s9-1 | M | T | `tests/master_test.py`; CI job `master-test` |
| SRS-VER-004 | Multi-tenant isolation shall be independently certified by an audit whose findings are reproducible via the commands recorded in the audit. | ROAD s8-9 | M | I | `docs/ISOLATION_AUDIT.md` §8 |
| SRS-VER-005 | Every notebook in `notebooks/*.ipynb` shall execute top-to-bottom in a clean environment without error, at least nightly. | ROAD s9-6 | M | T | `.github/workflows/notebook-repro.yml` |

## 4. Traceability

Every requirement in §3 carries a **verifying artifact** column. The full forward-and-backward traceability matrix (SRS → SDD → STR) is maintained as a table in the SDD (`docs/DID/SDD.md`) and is duplicated in the STR (`docs/DID/STR.md`) with the observed test outcomes.

The rule for a requirement to be considered *verified* is: the named verifying artifact exists, runs green in CI, and would fail if the requirement were violated. An artifact that exists but does not exercise the requirement is not a verifier.

## 5. Quality attributes (ISO/IEC 25010)

| Attribute | Requirement |
|---|---|
| Functional correctness | Every functional requirement (§3.1) has a test or inspection that verifies it. |
| Reliability | The discovery loop is deterministic under fixed seeds (SRS-FUN-047). Webhook idempotency is enforced at the database layer (SRS-SEC-003). |
| Performance efficiency | Bounded by SRS-PER-001 through SRS-PER-004. |
| Usability | Every UI output carries an epistemic badge (SRS-FUN-090); WCAG 2.1 AA contrast (SRS-FUN-093). |
| Security | Tenant isolation (SRS-FUN-080), JWT discipline (SRS-SEC-001), Stripe webhook verification (SRS-SEC-003). |
| Maintainability | Single conda environment (D10); single backend package layout (D8); no cross-module ORM shadowing (each module's public surface is documented in its docstring). |
| Portability | macOS only, by design (D2). No claims of portability to Linux/Windows beyond the CI Ubuntu runner used for tests. |
| Testability | Master test harness (SRS-VER-003); nightly notebook reproducibility (SRS-VER-005). |

## 6. What is not in scope

- Physical hardware of any kind. No satellite, laser, UAV, rectenna, or power-transmission hardware is claimed to exist or to be required.
- A government-contract deliverable. This SRS is a research artifact; the DID structure is a review framework, not a delivery vehicle.
- Multi-user concurrent SaaS operation beyond the tested isolation guarantees.
- Cloud deployment (D2).
- Any claim of optimality for the CLEAR-D method; the claim is that CLEAR-D produces *verified feasible* architectures, not that it is optimal among all methods.

## 7. Open items and honest limitations

- **SRS-FUN-091** (UI audit for epistemic status) is marked **PARTIAL**. The infrastructure exists; the audit is a Sprint 7 s7-9 follow-up that remains open (P34 in `docs/ROADMAP_STATUS.md`).
- **SRS-PER-004** (bundle size) is a documented limit (P31), not a hard requirement.
- **P5** (Han et al. citation) and **C-3** (MUC-G4 characterization) are open per `docs/CITATION_AUDIT.md`. Neither affects a requirement in this SRS directly, but the SRS-VER-002 requirement is the mechanism by which they are tracked.
- **Requirements derived from external standards (ANSI Z136.1, FCC Part 1.1310)** cite the standards by designation; the specific numeric limits are marked unverified against a current standards source in `docs/CITATION_AUDIT.md` §4.1–§4.2.

Signed: Kian Mansouri Jamshidi
