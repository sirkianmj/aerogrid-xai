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
| H1 | Predictive beam tracking improves expected energy delivery over position-only tracking, within disclosed uncertainty | `PARTIAL` | `backend/tests/test_h1_predictive_tracking.py` (4 tests). Mechanism covered on a declared scope; "within disclosed uncertainty" clause not covered. See H1 scope below. |
| H2 | Joint NSGA-II optimization of energy and topology improves resilience over independent UAV management | `PARTIAL` | `backend/tests/test_nsga2.py` verifies NSGA-II primitives (dominance, crowding, hypervolume). No test constructs a matched independent-management baseline. |
| H3 | Atmosphere-aware optimization reduces energy-transfer failures vs weather-independent scheduling | `PARTIAL` | `backend/tests/test_h3_atmosphere_scheduling.py` (4 tests). Mechanism covered on a declared weather distribution; "optimization" is a greedy max-forecast scheduler and the failure criterion is an operational threshold, not a spec-derived metric. See H3 scope below. |
| H4 | Uncertainty-aware decisions are more robust under environmental variability than point estimates | **UNCOVERED** | Tier 2 estimates carry intervals (`test_tier2.py`), but no test measures decision robustness under environmental noise with vs without uncertainty conditioning. |
| H5 | The two-tier architecture allows engineers to identify dominant factors with fidelity to the model's own logic | `COVERED` | `test_tier1.py`, `test_xai_fidelity_audit.py`; audit at `docs/XAI_FIDELITY_AUDIT.md`. |
| H6 | PWL-encoded Z3 verification proves feasibility or infeasibility within a disclosed approximation error before full simulation | `COVERED` | `test_pwl.py`, `test_pwl_tune.py`, `test_z3_end_to_end.py`, `test_scientific_validation/test_*`. |
| H7 | Hybrid laser+microwave architectures outperform single-modality for annual availability in most regions | **UNCOVERED** | The `Hybrid_Link` modality exists and the MPE constraint fires on both mechanisms (`test_encoder_physics.py`), but no test computes annual availability across regions. |
| H8 | Thermal management is the dominant limiting factor on continuous high-power laser reception for small UAVs | `PARTIAL` | `test_thermal.py`, `test_receiver.py` verify the thermal model; no test demonstrates dominance relative to other factors. |
| H9 | Closed-loop CLEAR-D discovers architectures with higher verified feasibility than generative search without unsat-core feedback, at equal computational budget | `COVERED` | `test_h9_convergence.py` (mutation-level, 40% faster than random); `notebooks/06_unsat_core_ablation.ipynb`; `notebooks/10_clear_d_end_to_end.ipynb` (3.29× mechanism-level). The loop-level comparison is documented as non-informative on the current generator, per HANDOFF §4b. |
| H10 | The coupled electro-thermal model predicts thermal runaway thresholds consistent with experimental receiver data within uncertainty bounds | `PARTIAL` | `test_thermal.py` verifies the runaway boundary within the model; comparison against external measured data is not performed (the Han et al. paper is [UNVERIFIED] per P5). |
| H11 | The two-tier controller achieves explanation fidelity 1.0 (by construction) while achieving prediction accuracy within 5% of an end-to-end opaque controller | `PARTIAL` | Fidelity = 1.0 is `COVERED` (`test_xai_fidelity_audit.py`). The "within 5% of opaque" half is not tested — no opaque controller exists to compare against. |
| H12 | Closed-loop refinement reduces epsilon by at least 50% over 100 operational cycles | `COVERED` | `test_pwl_tune.py::test_h12_epsilon_reduces_by_half_over_100_cycles`; `notebooks/08_closed_loop_refinement.ipynb`; `notebooks/10_clear_d_end_to_end.ipynb` (ratio 0.125). |

### H1 scope

The H1 test asserts a comparative claim (predictive vs position-only)
on a declared distribution. Parameters, motion families, and metric
are declared in the test module docstring and summarised here.

- Beam radius 17 m, slew latency 2 s, state noise sigma 5 m, n = 400.
- Motion: held-heading (linear) and constant-turn (|omega| <= 0.15
  rad/s). Speed uniform in [5, 25] m/s.
- Metric: mean pointing efficiency eta = exp(-2 delta^2 / w^2).
  Multiplicative in the link budget, so the mean is proportional to
  expected delivered energy.

Observed on this scope:

| Quantity | Value |
|---|---|
| Position-only eta (linear) | 0.07 |
| Predictive eta (linear) | 0.45 |
| Gain at L = 1, 2, 3, 5 s | +0.14, +0.39, +0.43, +0.45 |
| Linear family gain | +0.93 |
| Turning family gain | +0.87 |

Not covered: the claim's "within disclosed uncertainty" clause. The
test uses a point estimate perturbed by Gaussian noise, not the
conformal interval that TrajectoryEstimate.radius_m provides. No
controller in the repository consumes that interval; adding one is a
design change, not a test.

Known limitation: the constant-turn family produces arc deviation of
a few metres over the tracking horizon, small against the 17 m beam
radius. The predictor is only lightly penalized. A stronger
adversarial case would require turn rates producing deviations
comparable to the beam radius. That regime is not tested.

### H3 scope

The H3 test compares two scheduling policies on a declared weather
distribution. It is a design experiment: no scheduler exists in the
repository (`grep -rn 'schedule' backend/app/` returns no relevant
hits). The test constructs both policies and compares them.

- Weather-independent policy: round-robin over UAVs, ignoring weather.
- Atmosphere-aware policy: for each slot, compute forecast
  atmospheric transmittance for every UAV and pick the maximum.

Declared scope:

- Fleet: 6 UAVs at fixed slant paths 500, 1000, 2000, 3000, 4000,
  5000 m. Wavelength 1064 nm.
- Weather per slot: log-normal visibility (median 15 km, log-sigma
  0.6); Beta(2, 5) cloud factor. Slots drawn independently.
- Forecast: truth plus Gaussian noise (visibility sigma 2 km, cloud
  sigma 0.10), clipped to valid ranges.
- Failure criterion: actual transmittance below eta_min = 0.35.
- Schedule: 12 slots; both policies attempt 12 transfers, so the
  denominators match.
- Repeats: 400 schedules per condition.

Observed:

| Condition | aware | independent | gap |
|---|---|---|---|
| Constant weather (scale 0.0) | 0.000 | 8.000 | +8.000 |
| Half variance (0.5) | -- | -- | +7.830 |
| Full declared (1.0) | 0.003 | 7.155 | +7.152 |
| 1.5x variance | -- | -- | +6.340 |

Mechanism result: on this declared scope, atmosphere awareness
strictly reduces failures, and the gap remains positive across the
tested variance range.

Non-monotonicity: the marginal value of awareness is not monotone in
weather variance. At low variance the fixed effect of path-length
choice dominates and awareness nearly eliminates failures; at high
variance some slots are bad enough that even the best UAV falls
below threshold and there is nothing left for awareness to recover.
The gap peaks at low variance (8.00) and decreases toward higher
variance (6.34 at 1.5x). This was discovered when a test asserting
monotonicity failed during development; the test now asserts only
that the gap stays positive across the range.

Not covered:

- "Optimization": the aware policy is a greedy max-forecast choice,
  not a multi-slot optimizer. A scheduler that forecasts further
  ahead, or trades off across slots, is not tested.
- The failure criterion (transmittance < 0.35) is an operational
  threshold, not a spec-derived metric. Changing it changes the
  absolute numbers and, in principle, the direction of the gap.
- Weather is synthetic. No real meteorological data is used. The
  forecast model is Gaussian noise around truth, not a real
  forecasting system with bias, correlation, or regime changes.
- No integration with the platform's actual policy or control layer;
  none exists in the repository.

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

## Epistemic hierarchy audit

Every UI feature panel and every scientific backend endpoint has been
audited for Section 21 epistemic tagging. See
`docs/EPISTEMIC_HIERARCHY_AUDIT.md`. Result: 6/6 top-level panels
correctly wrapped in `TaggedOutput`; all scientific endpoints except
three `/orbital/*` routes carry an `epistemic_tag` field. Four findings
(F-1 through F-4) recorded for follow-up; none is a live defect.

## UI panels (post-Sprint-10 instrument work)

Each UI panel that renders a claim-bearing artifact is listed here with
its verifying tests. A panel that displays a number without a test that
would fail if the number were wrong does not belong in the instrument.

| Panel / capability | Epistemic tag | Verifying tests |
|---|---|---|
| Mission Control pipeline view | per-stage (`simulation_result` at the wrapper) | `backend/tests/test_mission_state.py` (20) + `frontend/src/features/MissionControl/MissionControl.test.tsx` (11) |
| Mission configuration bar | drives input to `/mission/state` | `frontend/src/features/MissionControl/MissionConfigBar.test.tsx` (7) + `backend/tests/test_mission_state.py` (4 config-parameter tests) |
| CLEAR-D Discovery dashboard | `simulation_result` | `backend/tests/test_discovery_api.py` (14) + `frontend/src/features/ClearDDashboard/ClearDDashboard.test.tsx` (12) |
| FANET graph | `simulation_result` | `backend/tests/test_mission_state.py` (node_list/link_list assertions) + `frontend/src/features/Fanet/FanetGraph.test.tsx` (13) |
| Animated Globe + time control | `simulation_result` | `frontend/src/features/Globe/GlobeControls.test.tsx` (12) + `backend/tests/test_orbital_api.py` (14) |
| Ground-anchored CLEAR-D | `simulation_result` | `backend/tests/test_generator.py` (4 pin tests) + `backend/tests/test_discovery_api.py` (2 pin tests) |
| Tier 2 atmospheric uncertainty bands | `simulation_result` | `backend/tests/test_mission_state.py` (2 interval tests) + `backend/tests/test_tier2.py` (existing) |

The epistemic tags are enforced by the `TaggedOutput` component at the
type level (`frontend/src/components/EpistemicBadge/`). See
`docs/EPISTEMIC_HIERARCHY_AUDIT.md` for the enforcement audit.

## Citation audit

Every citation referenced by the claims in this document has been
collected and classified in `docs/CITATION_AUDIT.md`. That audit
distinguishes three independent questions — is the citation
well-formed, does the source exist, do the attributed values appear in
the source — and reports the state of each. The High-priority items
that require external access are P5 (Han et al. DOI unresolved) and
C-3 (MUC-G4 characterization unverified).

## Enforcement

`tests/master_test.py` runs the backend, frontend, and notebook phases
and fails on any non-PASS. The `master-test` CI job is a required
branch-protection context. A change to a claim without a corresponding
change here (or a new test) fails code review; the roadmap rule is that
the uncovered state renders the claim invalid, not merely weak.
