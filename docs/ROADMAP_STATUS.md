# AeroGrid-XAI Roadmap Status

Authoritative tracker of roadmap completion. Updated on every merged PR.

Runtime: native macOS, Miniforge (conda-forge). No Docker, no Kubernetes,
no cloud VMs. Z3 is the only formal-verification tool; no Lean.

Branch protection on `main`:
- Required checks: backend, frontend, formal-verification, cla-check
- `enforce_admins: true`, `strict: true`
- Force-push and branch deletion blocked
- Conversation resolution required
- Zero required approving reviews (solo maintainer)

## Phase 0 — Repository, Legal & Commercial

| ID | Task | Status |
|----|------|--------|
| p0-1 | Monorepo structure | COMPLETE |
| p0-2 | Dual-license files (AGPL-3.0 + Commercial EULA) | COMPLETE (external counsel review skipped by maintainer, documented in LICENSING_MATRIX) |
| p0-3 | Contributor License Agreement | COMPLETE (CLA.md + CI enforcement) |
| p0-4 | README commercial section | COMPLETE (commercial contact is a placeholder) |
| p0-5 | Component license matrix | COMPLETE |
| p0-6 | Defensive publication record | COMPLETE (docs/DEFENSIVE_PUBLICATION.md) |

## Sprint 0 — Foundation & CI/CD

| ID | Task | Status |
|----|------|--------|
| s0-1 | GitHub repo + branch protection | COMPLETE (4 required checks: backend, frontend, formal-verification, cla-check) |
| s0-2 | Dual-license + CLA + LICENSING_MATRIX | COMPLETE |
| s0-3 | Miniforge env `aerogrid` | COMPLETE |
| s0-4 | Native PostgreSQL + Redis + scripts | COMPLETE (scripts/start_services.sh, stop_services.sh, status_services.sh) |
| s0-5 | Backend FastAPI scaffold | COMPLETE |
| s0-6 | Frontend scaffold | COMPLETE |
| s0-7 | CI pipeline (backend, frontend, formal-verification, cla-check) | COMPLETE |
| s0-8 | Notebook 01 — TRL benchmark validation | COMPLETE (PR #2) |
| s0-9 | Cascaded link budget scientific gate | COMPLETE (PR #3) |

## Sprint 1 — Digital Twin Core: Orbital Mechanics

| ID | Task | Status |
|----|------|--------|
| s1-1 | Skyfield integration | COMPLETE (PR #4) |
| s1-2 | TLE ingestion + propagation | COMPLETE (PR #4) |
| s1-3 | Visibility window calculator | COMPLETE (PR #5) |
| s1-4 | Eclipse period detection | COMPLETE (PR #5) |
| s1-5 | Geographic region model | COMPLETE (PR #6) |
| s1-6 | Notebook 02 — LEO vs GEO visibility | COMPLETE (PR #6) |
| s1-7 | No hard-coded positions | COMPLETE (PR #6) |

## Sprint 2a — Stage A receiver stack

| ID | Task | Status |
|----|------|--------|
| s2-1 | PLC efficiency model eta_PLC(T) | COMPLETE (PR #8) |
| s2-2 | TE efficiency model eta_TE(T) | COMPLETE (PR #8) |
| s2-3 | Corrected attribution: Sb2Se3 in thermal conduction, NOT Seebeck | COMPLETE (PR #8) |

## Sprint 2b — Two-node thermal model + runaway boundary

| ID | Task | Status |
|----|------|--------|
| s2-4 | Two-node lumped thermal model (dT_PLC/dt, dT_TE/dt) | COMPLETE (PR #9) |
| s2-5 | Thermal runaway boundary P_max(T_amb, v) | COMPLETE (PR #9) |

## Sprint 2c — Efficiency surface + dimensional consistency

| ID | Task | Status |
|----|------|--------|
| s2-6 | Notebook 03 — Efficiency surface eta(P, T, v) | COMPLETE (PR #11) |
| s2-7 | Scientific gate: dimensional consistency | COMPLETE (PR #11) |

## Sprint 3 — Stage B: PWL-SMT Constraint Encoding

| ID | Task | Status |
|----|------|--------|
| s3-1 | PWL approximation builder | COMPLETE (PR #12) |
| s3-2 | Error tracker (epsilon per constraint family) | COMPLETE (PR #12) |
| s3-3 | Incremental Linearization encoding to SMT-LIB | COMPLETE (PR #13) |
| s3-4 | Hierarchical decomposition (k=5-15 intra-cluster + inter-cluster flow) | COMPLETE (PR #14) |
| s3-5 | Regulatory constraint encoding (ANSI Z136.1 MPE + FCC Part 1.1310) | COMPLETE (PR #15) |
| s3-6 | Notebook 04 — PWL accuracy vs. segments | COMPLETE (PR #16) |
| s3-7 | Notebook 05 — Hierarchical vs. monolithic Z3 | COMPLETE (PR #17) — see gate reformulation below |
| s3-8 | Scientific gate: SAT verdict is conservative | PENDING — see gate note below |

### s3-7 gate reformulation (Rev. 2 → Rev. 3)

The Rev. 2 roadmap gate for s3-7 was:

> Hierarchical solves >50 nodes; monolithic times out.

The measurement in Notebook 05 (PR #17) does not reproduce this claim
on satisfiable, structurally-independent cluster constraints. Measured
hierarchical-versus-monolithic ratios were 0.78x–0.96x — hierarchical
10–20% slower — because Z3's internal preprocessing detects structural
independence and decomposes the problem internally. External per-cluster
decomposition adds Python-side setup cost without saving solve time.
The spec's asymptotic claim (Section 34.3, "SMT solving is exponential
in the worst case") is correct in principle but is not reproduced when
per-cluster subproblems solve in ~10 ms each.

The reformulated gate, which the measurement supports, is:

> (a) Hierarchical solve time scales linearly with cluster count.
> (b) Composition overhead is bounded and small in absolute terms
>     (sub-second at 64 clusters).
> (c) The Section 34.3 soundness invariant — SAT iff every cluster SAT
>     and inter-cluster flow SAT — is preserved. This is covered by
>     15 tests in backend/tests/test_hierarchical.py.

Reason for reformulation: the original claim is a design-intent
statement, not a measured property. Replacing it with a measured claim
is consistent with the epistemic hierarchy (Section 21) and with the
project rule that any scientific claim not covered by test is invalid
(roadmap s9-7).

### s3-8 gate note (pending)

The Rev. 2 roadmap gate for s3-8 is:

> SAT verdict is conservative — Fuzz test against random architectures —
> Never falsely declares infeasible architecture feasible.

The literal claim is not consistent with the PWL direction selected by
Section 34.2 of the spec. Section 34.2 writes f_hat(x) <= f(x) and calls
it a "sound over-approximation". Under that direction:

  - UNSAT is definitive: an empty encoded region implies an empty true
    region.
  - SAT is necessary but not sufficient: the encoded region is a
    superset of the true region, and a SAT witness may still violate
    the true constraint.

Under the spec's literal direction, the correct soundness statement is
"UNSAT never falsely declares a feasible architecture infeasible", not
"SAT never falsely declares an infeasible architecture feasible". The
discrepancy is documented in the docstrings of
backend/app/verification/pwl.py and backend/app/verification/encoder.py.

s3-8 will be implemented in the next commit. The plan is to fuzz-test
the UNSAT direction (the direction that is sound under the spec's
literal encoding) and to record the direction question prominently in
the test module rather than silently resolving it. If the project
requires the strict "SAT is conservative" claim, the fix is to flip
the PWL direction from f_hat <= f to f_hat >= f. That is a localized
change to the sampling loop in pwl.py and would require re-running
every downstream test.

## Sprints 4–12

Not yet started. See the Master Engineering Roadmap (Rev. 2).
