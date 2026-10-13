# Scientific claims — test coverage map

**Rule (roadmap s9-7):** any scientific claim in the specification that
is not covered by an automated test is **invalid**. This document is
the authoritative map from claim to test. A claim is *covered* if and
only if some test in `backend/tests/`, `frontend/src/**/*.test.ts(x)`,
or a notebook cell guarded by an assertion would fail if the claim were
false.

This file is maintained alongside the tests. When a new claim is added
to the specification, it must appear below with a status of either
`COVERED` (with the test path) or `UNCOVERED` (with a rationale for why
a test does not yet exist). There is no third state.

Status legend:

- `COVERED` — a test exists whose failure would falsify the claim.
- `PARTIAL` — a test covers the claim's mechanism but not its full
  stated scope; the gap is named.
- `UNCOVERED` — no test exercises the claim. **The claim is invalid
  until coverage is added.**
- `N/A` — the item is not a scientific claim (e.g. an architectural
  invariant, which is tested structurally rather than falsified).

## Research hypotheses (specification Section 27)

| ID | Claim (abridged) | Status | Test(s) |
|----|------------------|--------|---------|
| H1 | Predictive beam tracking improves expected energy delivery over position-only tracking, within disclosed uncertainty | **UNCOVERED** | The trajectory predictor exists (`app/control/trajectory.py`) but no test compares it to a position-only baseline under matched conditions. Reported in the specification as a target experiment, not a result. |
| H2 | Joint NSGA-II optimization of energy and topology improves resilience over independent UAV management | `PARTIAL` | `backend/tests/test_nsga2.py` verifies NSGA-II primitives (dominance, crowding, hypervolume). No test constructs a matched independent-management baseline. |
| H3 | Atmosphere-aware optimization reduces energy-transfer failures vs weather-independent scheduling | **UNCOVERED** | `test_atmosphere.py` verifies the physics; no end-to-end test compares the two scheduling regimes. |
| H4 | Uncertainty-aware decisions are more robust under environmental variability than point estimates | **UNCOVERED** | Tier 2 estimates carry intervals (`test_tier2.py`), but no test measures decision robustness under environmental noise with vs without uncertainty conditioning. |
| H5 | The two-tier architecture allows engineers to identify dominant factors with fidelity to the model's own logic | `COVERED` | `test_tier1.py`, `test_xai_fidelity_audit.py`; audit at `docs/XAI_FIDELITY_AUDIT.md`. |
| H6 | PWL-encoded Z3 verification proves feasibility or infeasibility within a disclosed approximation error before full simulation | `COVERED` | `test_pwl.py`, `test_pwl_tune.py`, `test_z3_end_to_end.py`, `test_scientific_validation/test_*`. |
| H7 | Hybrid laser+microwave architectures outperform single-modality for annual availability in most regions | **UNCOVERED** | The `Hybrid_Link` modality exists and the MPE constraint fires on both mechanisms (`test_encoder_physics.py`), but no test computes annual availability across regions. |
| H8 | Thermal management is the dominant limiting factor on continuous high-power laser reception for small UAVs | `PARTIAL` | `test_thermal.py`, `test_receiver.py` verify the thermal model; no test demonstrates dominance relative to other factors. |
| H9 | Closed-loop CLEAR-D discovers architectures with higher verified feasibility than generative search without unsat-core feedback, at equal computational budget | `COVERED` | `test_h9_convergence.py` (mutation-level, 40% faster than random); `notebooks/06_unsat_core_ablation.ipynb`; `notebooks/10_clear_d_end_to_end.ipynb` (3.29× mechanism-level). The loop-level comparison is documented as non-informative on the current generator, per HANDOFF §4b. |
| H10 | The coupled electro-thermal model predicts thermal runaway thresholds consistent with experimental receiver data within uncertainty bounds | `PARTIAL` | `test_thermal.py` verifies the runaway boundary within the model; comparison against external measured data is not performed (the Han et al. paper is [UNVERIFIED] per P5). |
| H11 | The two-tier controller achieves explanation fidelity 1.0 (by construction) while achieving prediction accuracy within 5% of an end-to-end opaque controller | `PARTIAL` | Fidelity = 1.0 is `COVERED` (`test_xai_fidelity_audit.py`). The "within 5% of opaque" half is not tested — no opaque controller exists to compare against. |
| H12 | Closed-loop refinement reduces epsilon by at least 50% over 100 operational cycles | `COVERED` | `test_pwl_tune.py::test_h12_epsilon_reduces_by_half_over_100_cycles`; `notebooks/08_closed_loop_refinement.ipynb`; `notebooks/10_clear_d_end_to_end.ipynb` (ratio 0.125). |

## Real-world benchmark claims (specification Section 6)

| Source | Figure | Status | Test(s) |
|--------|--------|--------|---------|
| PowerLight (TRL 6) | ~1 kW delivered at up to 5,000 ft (1,524 m) | `COVERED` | `test_scientific_validation/test_powerlight.py` (consistency within 5%); `notebooks/01_trl_benchmark_validation.ipynb`. |
| Xidian (TRL 4-5) | 20.8% on-target DC-to-DC | `COVERED` | `test_scientific_validation/test_xidian.py` (within 5%). |
| Xidian (TRL 4-5) | 3-5% end-to-end wall-plug-to-battery | `COVERED` | `test_scientific_validation/test_xidian.py` (lands in band); `test_link_budget_gate.py::test_xidian_dual_report_both_figures_present`. |
| Overview Energy (TRL 5) | ~5,000 m altitude; ground-receiver analog | `COVERED` | `test_scientific_validation/test_overview_energy.py` (scope disclaimers preserved). |
| DARPA POWER (TRL 5) | >800 W over 8.6 km | `COVERED` | `test_scientific_validation/test_darpa_power.py` (transmission coefficient in plausible range; scope note preserved). |
| Han et al. (TRL 3) | 38.49% at 520 nm, 1.2 W/cm² | `COVERED` | `test_scientific_validation/test_han_et_al.py` (value preserved as a *receiver* efficiency). Note: citation verification remains open per **P5**. |

## Architectural invariants

| Invariant | Status | Test(s) |
|-----------|--------|---------|
| Tier 2 never reaches the Tier 1 action interface | `COVERED` | `test_static_analyzer.py::test_real_control_package_is_clean` (transitive call-graph check). |
| Tier 1 explanation is the model's literal computation trace | `COVERED` | `test_tier1.py` (score == sum of step weights); `test_xai_fidelity_audit.py` (100-point sweep). |
| Tier 2 estimates cannot override caller-supplied candidate values | `COVERED` | `test_tier1.py::test_candidate_overrides_estimate_for_same_key`; `test_xai_fidelity_audit.py::test_estimates_cannot_override_candidate_across_sweep`. |
| Malformed input does not crash a Tier 1 decision | `COVERED` | `test_tier1.py` (F-1 regressions, per `docs/XAI_FIDELITY_AUDIT.md`). |
| Multi-tenant isolation enforced by PostgreSQL RLS at the database layer | `COVERED` | `test_rls_isolation.py` (9 tests, including F-1 revocation); `docs/ISOLATION_AUDIT.md`. |
| Quota exceeded returns HTTP 429 with Retry-After, not a crash | `COVERED` | `test_saas_quota.py`; `test_tradespace_api.py::test_run_returns_429_when_free_limit_exhausted`. |
| Admin endpoints require superadmin role | `COVERED` | `test_saas_admin_routes.py` (401/403/200 for viewer/admin/superadmin). |
| PWL is a sound over-approximation (never falsely declares infeasible architecture feasible) | `COVERED` (with s3-8 reformulation note) | `test_pwl.py`, `test_fuzz_soundness.py`. The Rev. 2 wording and the reformulation are recorded in `docs/ROADMAP_STATUS.md`. |

## Constraints and modelling limits (carried forward, not claims)

These are explicitly documented limitations, not claims, so they are
`N/A` for the coverage rule. They are listed here so the falsifiable
claims above are not confused with them:

- **P5** — the Han et al. citation lacks a DOI; paper existence is
  unverified. The claim *covered* is only that the value is preserved
  in the benchmark table.
- **P21** — Kruse-Kim coefficients cited by reference, not cross-checked
  against source PDFs.
- **P26** — the generator does not verify combined UAV supply vs.
  demand; not a claim but a documented generator limitation.
- **P31** — frontend bundle size.
- **P32/P33** — cosmetic jsdom warnings in two frontend test files.
- **P34** — Sprint 7 s7-7 and s7-9 partial; UI audit pending.
- **Notebook 10 F-1** — `eta_plc` has a material discontinuity at
  `T_MAX_K`; the PWL domain is restricted to the pre-cutoff band. See
  the notebook's Stage A markdown.

## Enforcement

`tests/master_test.py` runs the backend, frontend, and notebook phases
and fails on any non-PASS. The `master-test` CI job is a required
branch-protection context. A change to a claim without a corresponding
change here (or a new test) fails code review; the roadmap rule is that
the uncovered state renders the claim invalid, not merely weak.
