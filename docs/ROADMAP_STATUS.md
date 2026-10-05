# AeroGrid-XAI Roadmap Status

Authoritative tracker of roadmap completion. Updated on every merged PR.

Runtime: native macOS, Miniforge (conda-forge). No Docker, no Kubernetes,
no cloud VMs. Z3 is the only formal-verification tool; no Lean.

Branch protection on main:
- Required checks: backend, frontend, formal-verification, cla-check
- enforce_admins: true, strict: true
- Force-push and branch deletion blocked
- Conversation resolution required
- Zero required approving reviews (solo maintainer)

## Phase 0 - Repository, Legal & Commercial

| ID | Task | Status |
|----|------|--------|
| p0-1 | Monorepo structure | COMPLETE |
| p0-2 | Dual-license files (AGPL-3.0 + Commercial EULA) | COMPLETE (external counsel review skipped by maintainer, documented in LICENSING_MATRIX) |
| p0-3 | Contributor License Agreement | COMPLETE (CLA.md + CI enforcement; CLA-assistant bot optional) |
| p0-4 | README commercial section | COMPLETE (commercial contact is a placeholder) |
| p0-5 | Component license matrix | COMPLETE |
| p0-6 | Defensive publication record | COMPLETE (docs/DEFENSIVE_PUBLICATION.md) |

## Sprint 0 - Foundation & CI/CD

| ID | Task | Status |
|----|------|--------|
| s0-1 | GitHub repo + branch protection | COMPLETE (4 required checks: backend, frontend, formal-verification, cla-check; enforce_admins=true) |
| s0-2 | Dual-license + CLA + LICENSING_MATRIX | COMPLETE |
| s0-3 | Miniforge env aerogrid | COMPLETE |
| s0-4 | Native PostgreSQL + Redis + scripts | COMPLETE (scripts/start_services.sh, stop_services.sh, status_services.sh) |
| s0-5 | Backend FastAPI scaffold | COMPLETE |
| s0-6 | Frontend scaffold | COMPLETE |
| s0-7 | CI pipeline (backend, frontend, formal-verification, cla-check) | COMPLETE |
| s0-8 | Notebook 01 - TRL benchmark validation | COMPLETE |
| s0-9 | Cascaded link budget scientific gate | COMPLETE |

## Sprint 1 - Digital Twin Core: Orbital Mechanics

| ID | Task | Status |
|----|------|--------|
| s1-1 | Skyfield integration | COMPLETE (validated against Spacetrack Report #3 test vector) |
| s1-2 | TLE ingestion + propagation | COMPLETE |
| s1-3 | Visibility window calculator | COMPLETE (validated against independent look-angle geometry invariants) |
| s1-4 | Eclipse period detection | COMPLETE (cylindrical model cross-validated against conical umbra model; agreement > 95%) |
| s1-5 | Geographic region model | COMPLETE |
| s1-6 | Notebook 02 - LEO vs GEO visibility | COMPLETE |
| s1-7 | No hard-coded positions | COMPLETE |

## Sprint 2a - Stage A receiver stack (PR #8)

| ID | Task | Status |
|----|------|--------|
| s2-1 | PLC efficiency model eta_PLC(T) | COMPLETE |
| s2-2 | TE efficiency model eta_TE(T) | COMPLETE |
| s2-3 | Corrected attribution: Sb2Se3 in thermal conduction, NOT Seebeck | COMPLETE |

## Sprint 2b - Two-node thermal model + runaway boundary (PR #9)

| ID | Task | Status |
|----|------|--------|
| s2-4 | Two-node lumped thermal model (dT_PLC/dt, dT_TE/dt) | COMPLETE |
| s2-5 | Thermal runaway boundary P_max(T_amb, v) | COMPLETE |

## Sprints 2c-12

Not yet started. See the Master Engineering Roadmap (Rev. 2).
