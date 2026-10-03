# AeroGrid-XAI Roadmap Status

Authoritative tracker of roadmap completion. Updated on every merged PR.

Runtime: native macOS, Miniforge (conda-forge). No Docker, no Kubernetes,
no cloud VMs. No Lean 4. Z3 is the only formal-verification tool.

## Phase 0 - Repository, Legal & Commercial

| ID | Task | Status |
|----|------|--------|
| p0-1 | Monorepo structure | COMPLETE |
| p0-2 | Dual-license files (AGPL-3.0 + Commercial EULA) | COMPLETE (external counsel review skipped by maintainer, documented in LICENSING_MATRIX) |
| p0-3 | Contributor License Agreement | COMPLETE (CLA.md + CI enforcement; CLA-assistant bot optional) |
| p0-4 | README commercial section | COMPLETE |
| p0-5 | Component license matrix | COMPLETE |
| p0-6 | Defensive publication record | COMPLETE (docs/DEFENSIVE_PUBLICATION.md) |

## Sprint 0 - Foundation & CI/CD

| ID | Task | Status |
|----|------|--------|
| s0-1 | GitHub repo + branch protection | COMPLETE (3 required checks, enforce_admins=true) |
| s0-2 | Dual-license + CLA + LICENSING_MATRIX | COMPLETE |
| s0-3 | Miniforge env `aerogrid` | COMPLETE |
| s0-4 | Native PostgreSQL + Redis + scripts | COMPLETE (scripts/start_services.sh, stop_services.sh, status_services.sh) |
| s0-5 | Backend FastAPI scaffold | COMPLETE |
| s0-6 | Frontend scaffold | COMPLETE |
| s0-7 | CI pipeline (backend, frontend, formal-verification) | COMPLETE |
| s0-8 | Notebook 01 - TRL benchmark validation | COMPLETE |
| s0-9 | Cascaded link budget scientific gate | COMPLETE |

## Sprint 1 - Digital Twin Core: Orbital Mechanics

| ID | Task | Status |
|----|------|--------|
| s1-1 | Skyfield integration | COMPLETE (validated against Spacetrack Report #3 test vector: |r| and |v| within 1 km and 0.01 km/s) |
| s1-2 | TLE ingestion + propagation | COMPLETE |
| s1-3 | Visibility window calculator | COMPLETE (validated against independent look-angle geometry invariants: sub-point zenith, antipode below horizon, continuity, one-window-per-orbit) |
| s1-4 | Eclipse period detection | COMPLETE (cylindrical model cross-validated against conical umbra model; agreement > 95%) |
| s1-5 | Geographic region model | COMPLETE |
| s1-6 | Notebook 02 - LEO vs GEO visibility | COMPLETE |
| s1-7 | No hard-coded positions | COMPLETE |

## Sprints 2-12

Not yet started. See the Master Engineering Roadmap (Rev. 2).
