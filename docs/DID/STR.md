# Software Test Report — AeroGrid-XAI

| Field | Value |
|---|---|
| Document identifier | AGRID-STR-001 |
| Version | 1.0 |
| Date | 2026-10-14 |
| Status | Baseline |
| Author | Kian Mansouri Jamshidi |
| Companion SRS | `docs/DID/SRS.md` |
| Companion SDD | `docs/DID/SDD.md` |
| Structure | Follows the DI-IPSC-81434 STR section layout (see SRS §1 note) |
| Repository state | `main` at commit `ea2141d` |

## 1. Scope

This is the Test Report for AeroGrid-XAI at commit `ea2141d`. It
records, for every requirement in `docs/DID/SRS.md`, the test item, the
verification method, and the observed outcome as of this commit.

The report is bounded. It does not re-derive the theoretical basis of
each requirement (that is the SRS's role) or restate the design
rationale (that is the SDD's role). It states what was run, what passed,
what was skipped, and what remains unverified.

The report is issued **against a specific commit** and is not valid for
any later state without re-execution. The `master-test` CI job is the
mechanism by which re-execution is enforced on every PR; the
`notebook-repro` workflow re-executes the notebooks nightly.

## 2. Referenced documents

| Ref | Document |
|---|---|
| SRS | `docs/DID/SRS.md` |
| SDD | `docs/DID/SDD.md` |
| CLAIMS | `docs/SCIENTIFIC_CLAIMS.md` |
| CITES | `docs/CITATION_AUDIT.md` |
| ISO | `docs/ISOLATION_AUDIT.md` |
| XAIA | `docs/XAI_FIDELITY_AUDIT.md` |
| DEFPUB | `docs/DEFENSIVE_PUBLICATION.md` |

## 3. Test items

### 3.1 Backend test suite

`backend/tests/` — 53 test modules at this commit. Total assertions
across the suite (test functions, counted by `grep -cE "^def test_"`)
is 1000+ as of the last full run.

### 3.2 Frontend test suite

`frontend/src/**/*.test.ts(x)` — 16 test modules. 163 test cases at this
commit.

### 3.3 Notebooks

`notebooks/*.ipynb` — 10 notebooks (01–08, 09, 10). Each is executed
top-to-bottom by the `master-test` job (structural verification) and by
the `notebook-repro` workflow (full execution).

### 3.4 Master test harness

`tests/master_test.py` — the composition harness invoked by the
`master-test` CI job. Passes when all three phases (backend, frontend,
notebooks) report 0 failures and 0 errors, and, with `--require-db`, 0
skips.

## 4. Test environment

| Component | Version |
|---|---|
| Python | 3.12.14 |
| Node | v20.20.2 |
| ruff | 0.16.9 |
| mypy | 2.3.1 (strict) |
| pytest | 9.1.1 |
| Z3 | 5.1.0 |
| NumPy | 2.5.3 |
| SciPy | 1.18.1 |
| PostgreSQL | 16 (service container in CI; local dev DB for the DB-backed subset) |
| React | 19.2.8 |
| Vite | 8.3.x |
| TypeScript | 6.0.x |
| Vitest | 4.1.x |

Runtime environment: native macOS (Miniforge conda env `aerogrid`);
CI runners are Ubuntu with a conda env built from `environment.yml`.
No Docker, no Kubernetes, no cloud VMs are used for tests beyond the
GitHub-hosted runners themselves (D2).

## 5. Test methods

| Method code | Method |
|---|---|
| T | Automated test (pytest, vitest, or a notebook assertion) |
| I | Inspection of a named document or module docstring by a reader |
| D | Demonstration via CI or a manual run recorded in the CI log |

Requirements marked `T` are exercised automatically on every PR via the
`master-test` CI job. Requirements marked `I` are documentary; they are
verified by a reader at merge time via the PR body and the diff. The
SRS accepts `I` as a verification method because for documentary
requirements (audits, claims maps) no automated check exists by design.

## 6. Test results

### 6.1 Full-suite outcomes at `ea2141d`

| Suite | Command | Result |
|---|---|---|
| Backend, all tests (no DB) | `pytest -q` from `backend/` | **1062 passed**, 0 failed, 0 errors |
| Backend, DB-backed subset | `pytest tests/test_rls_isolation.py tests/test_saas_routes.py tests/test_saas_billing_routes.py tests/test_saas_quota.py tests/test_saas_admin_routes.py` with PostgreSQL running | **64 passed**, 0 skipped |
| Frontend | `npm test` from `frontend/` | **163 passed**, 0 failed |
| Notebooks (structural) | `python tests/master_test.py --notebooks` | **10 verified**, RESULT: PASS |
| Master harness (full) | `python tests/master_test.py` | backend 1062 passed, frontend 163 passed, notebooks 10 verified → **RESULT: PASS** |

### 6.2 Continuous-integration outcomes at `ea2141d`

| Job | Purpose | Status |
|---|---|---|
| `backend` | ruff + mypy + pytest | green |
| `frontend` | oxlint + tsc + vitest + vite build | green |
| `formal-verification` | Z3 sanity check | green |
| `cla-check` | PR author in `signatures/cla-v1.json` | green |
| `rls-isolation` | DB-backed tests against an ephemeral PostgreSQL 16 | green |
| `master-test` | backend + frontend + notebooks, `--require-db` | green |

All six jobs are required branch-protection contexts. A PR that would
break any of them cannot merge.

### 6.3 Per-requirement outcomes

The table below names every requirement in the SRS with the test item
that verifies it and the observed outcome at `ea2141d`.

#### 6.3.1 Orbital and geographic (SRS-FUN-001 through SRS-FUN-005)

| Req | Test | Outcome |
|---|---|---|
| SRS-FUN-001 | `test_orbital.py`, `test_sgp4_reference.py` | PASS |
| SRS-FUN-002 | `test_visibility.py` | PASS |
| SRS-FUN-003 | `test_eclipse_conical.py` | PASS |
| SRS-FUN-004 | `test_region.py` | PASS |
| SRS-FUN-005 | `test_no_hardcoded_positions.py` | PASS |

#### 6.3.2 Wireless power transmission (SRS-FUN-010 through SRS-FUN-013)

| Req | Test | Outcome |
|---|---|---|
| SRS-FUN-010 | `test_beam_and_physical_link_budget.py` | PASS |
| SRS-FUN-011 | `test_link_budget.py` | PASS |
| SRS-FUN-012 | `test_link_budget_gate.py`, `test_xidian.py` | PASS |
| SRS-FUN-013 | `test_link_budget.py::test_end_to_end_efficiency_is_product_of_stages` | PASS |

#### 6.3.3 Atmosphere (SRS-FUN-020 through SRS-FUN-022)

| Req | Test | Outcome |
|---|---|---|
| SRS-FUN-020 | `test_atmosphere.py` | PASS |
| SRS-FUN-021 | `test_atmosphere.py` | PASS |
| SRS-FUN-022 | `test_tier2.py::test_gate_90pct_coverage_at_least_85pct` | PASS |

#### 6.3.4 Receiver and thermal (SRS-FUN-030 through SRS-FUN-033)

| Req | Test | Outcome |
|---|---|---|
| SRS-FUN-030 | `test_receiver.py`, `test_thermal.py` | PASS |
| SRS-FUN-031 | `test_receiver.py` | PASS |
| SRS-FUN-032 | `test_thermal.py` | PASS |
| SRS-FUN-033 | `test_thermal.py` | PASS |

#### 6.3.5 CLEAR-D discovery (SRS-FUN-040 through SRS-FUN-047)

| Req | Test | Outcome |
|---|---|---|
| SRS-FUN-040 | `test_grammar.py` | PASS |
| SRS-FUN-041 | `test_generator.py`, `test_generator_los.py` | PASS |
| SRS-FUN-042 | `test_unsat.py` | PASS |
| SRS-FUN-043 | `test_attribution.py` | PASS |
| SRS-FUN-044 | `test_h9_convergence.py`, `test_mutation.py` | PASS |
| SRS-FUN-045 | `test_z3_end_to_end.py::test_100_generations_completes_without_error` | PASS |
| SRS-FUN-046 | `test_nsga2.py` | PASS |
| SRS-FUN-047 | `test_discovery_determinism.py`, `test_z3_end_to_end.py::test_100_generations_is_deterministic_under_fixed_seed` | PASS |

#### 6.3.6 Two-tier XAI (SRS-FUN-050 through SRS-FUN-054)

| Req | Test | Outcome |
|---|---|---|
| SRS-FUN-050 | `tier1.py` inspection; `docs/XAI_FIDELITY_AUDIT.md` §4 | PASS (by inspection) |
| SRS-FUN-051 | `test_tier2.py`, `test_xai_fidelity_audit.py` | PASS |
| SRS-FUN-052 | `test_static_analyzer.py::test_real_control_package_is_clean` | PASS |
| SRS-FUN-053 | `test_tier1.py`, `test_xai_fidelity_audit.py` | PASS |
| SRS-FUN-054 | `test_explain.py::test_counterfactual_ablating_decisive_rule_flips_decision` | PASS |

#### 6.3.7 Formal verification (SRS-FUN-060 through SRS-FUN-064)

| Req | Test | Outcome |
|---|---|---|
| SRS-FUN-060 | `test_pwl.py` | PASS |
| SRS-FUN-061 | `test_pwl.py`, `test_pwl_tune.py` | PASS |
| SRS-FUN-062 | `test_fuzz_soundness.py` | PASS |
| SRS-FUN-063 | `test_hierarchical.py` | PASS |
| SRS-FUN-064 | `test_regulatory.py` | PASS |

#### 6.3.8 Closed-loop refinement (SRS-FUN-070 through SRS-FUN-074)

| Req | Test | Outcome |
|---|---|---|
| SRS-FUN-070 | `test_bayes.py` | PASS |
| SRS-FUN-071 | `test_bayes.py::test_posterior_variance_strictly_less_than_prior` | PASS |
| SRS-FUN-072 | `test_pwl_tune.py::test_h12_epsilon_reduces_by_half_over_100_cycles`; Notebook 10 | PASS (Notebook 10 measured ratio 0.125) |
| SRS-FUN-073 | `test_discrepancy.py` | PASS |
| SRS-FUN-074 | `test_causality.py` | PASS |

#### 6.3.9 SaaS (SRS-FUN-080 through SRS-FUN-084)

| Req | Test | Outcome |
|---|---|---|
| SRS-FUN-080 | `test_rls_isolation.py`; `docs/ISOLATION_AUDIT.md` | PASS |
| SRS-FUN-081 | `test_rls_isolation.py::test_app_role_with_unset_guc_sees_zero_rows` | PASS |
| SRS-FUN-082 | `test_saas_auth.py` | PASS |
| SRS-FUN-083 | `test_saas_quota.py` | PASS |
| SRS-FUN-084 | `test_saas_admin_routes.py` | PASS |

#### 6.3.10 Epistemic hierarchy (SRS-FUN-090 through SRS-FUN-093)

| Req | Test | Outcome |
|---|---|---|
| SRS-FUN-090 | `EpistemicBadge.test.tsx` | PASS |
| SRS-FUN-091 | UI audit | **PARTIAL** — infrastructure exists; formal audit is P34, open |
| SRS-FUN-092 | `XAITrace.test.tsx` | PASS |
| SRS-FUN-093 | `contrast.test.ts` | PASS |

#### 6.3.11 Performance (SRS-PER-001 through SRS-PER-004)

| Req | Test | Outcome |
|---|---|---|
| SRS-PER-001 | `test_z3_end_to_end.py` | PASS (0.23 s for the 100-generation test) |
| SRS-PER-002 | `Telemetry.test.tsx` | PASS |
| SRS-PER-003 | `notebooks/05_smt_scaling.ipynb` | PASS |
| SRS-PER-004 | `npm run build` | PASS with the documented bundle-size advisory (P31) |

#### 6.3.12 Interface (SRS-INT-001 through SRS-INT-004)

| Req | Test | Outcome |
|---|---|---|
| SRS-INT-001 | `test_health.py` | PASS |
| SRS-INT-002 | `test_health.py` | PASS |
| SRS-INT-003 | `test_tradespace_api.py::test_openapi_lists_all_routers` | PASS |
| SRS-INT-004 | `test_telemetry_ws.py` | PASS |

#### 6.3.13 Safety (SRS-SAF-001 through SRS-SAF-004)

| Req | Test | Outcome |
|---|---|---|
| SRS-SAF-001 | `test_regulatory.py` | PASS |
| SRS-SAF-002 | `test_regulatory.py` | PASS |
| SRS-SAF-003 | `test_encoder_physics.py`, `test_architecture_encoder.py` | PASS |
| SRS-SAF-004 | `test_dimensional_consistency.py` | PASS |

#### 6.3.14 Security (SRS-SEC-001 through SRS-SEC-003)

| Req | Test | Outcome |
|---|---|---|
| SRS-SEC-001 | `test_saas_auth.py` | PASS |
| SRS-SEC-002 | `docs/ISOLATION_AUDIT.md` §4.3 | PASS (by inspection) |
| SRS-SEC-003 | `test_saas_billing_routes.py` | PASS |

#### 6.3.15 Verification / certification (SRS-VER-001 through SRS-VER-005)

| Req | Test | Outcome |
|---|---|---|
| SRS-VER-001 | `docs/SCIENTIFIC_CLAIMS.md` | PASS (by inspection) |
| SRS-VER-002 | `docs/CITATION_AUDIT.md` | PASS (by inspection; open items P5, C-3 recorded) |
| SRS-VER-003 | `tests/master_test.py`; `master-test` CI job | PASS |
| SRS-VER-004 | `docs/ISOLATION_AUDIT.md` §8 | PASS (by inspection) |
| SRS-VER-005 | `.github/workflows/notebook-repro.yml` | PASS (workflow present; first scheduled run pending) |

## 7. Anomalies and open items

| ID | Description | Impact on this report |
|---|---|---|
| SRS-FUN-091 | UI audit for epistemic status is P34 | **PARTIAL** — infrastructure tested; audit not yet performed |
| SRS-VER-005 | First scheduled nightly run of `notebook-repro.yml` has not yet occurred | Workflow is committed and its execute loop was simulated locally; the scheduled run is the definitive validation |
| P5 | Han et al. citation lacks DOI | No direct impact on any test; tracked in `CITATION_AUDIT.md` |
| C-3 | MUC-G4 characterization unverified | No impact on the code; the novelty argument in `DEFENSIVE_PUBLICATION.md` §4.2 depends on it |
| P21 | Kruse-Kim coefficient values not cross-checked against sources | The code paths are tested for form; the specific values are what remains unverified |
| — | None of the above causes a required CI check to fail | All six checks green at `ea2141d` |

## 8. Coverage summary

| Category | Requirements | PASS | PARTIAL | UNVERIFIED |
|---|---|---|---|---|
| Functional | 47 | 46 | 1 (SRS-FUN-091) | 0 |
| Performance | 4 | 4 | 0 | 0 |
| Interface | 4 | 4 | 0 | 0 |
| Safety | 4 | 4 | 0 | 0 |
| Security | 3 | 3 | 0 | 0 |
| Verification | 5 | 4 | 1 (SRS-VER-005, pending first nightly) | 0 |
| **Total** | **67** | **65** | **2** | **0** |

The report does not claim **100%** PASS. Two requirements are PARTIAL
with reasons stated. Neither is a failure; both are documented and
tracked.

## 9. Certification

Within the method and the bounds described in §1 and §5, the software
at commit `ea2141d` satisfies every M-priority requirement in the SRS
for which an automated verifying artifact exists, and satisfies every
documentary (I-method) requirement for which the named audit or map
exists and is internally consistent.

The remaining PARTIAL items are:

1. **SRS-FUN-091** — the UI audit is infrastructure-verified but the
   written audit is deferred. Expected to close with a Sprint 7 s7-9
   follow-up.
2. **SRS-VER-005** — the nightly workflow exists and its execute loop
   was simulated locally; the first scheduled run is the definitive
   validation. Expected to close after 06:00 UTC on the day following
   this report.

The report does not claim that AeroGrid-XAI is free of defects. It
claims that the requirements as stated in the SRS are verified against
the code at `ea2141d` by the mechanism named in each row, and that the
two PARTIAL items are honestly reported rather than papered over.

Signed: Kian Mansouri Jamshidi
