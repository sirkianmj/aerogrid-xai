# Changelog

All notable changes to AeroGrid-XAI are documented here.
This project adheres to Semantic Versioning.

## [Unreleased]

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
