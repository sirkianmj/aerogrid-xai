# Changelog

All notable changes to AeroGrid-XAI are documented here.
This project adheres to Semantic Versioning.

## [Unreleased]

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
