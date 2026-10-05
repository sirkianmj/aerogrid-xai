AeroGrid-XAI Licensing Matrix

This document declares the license that applies to each component of
the repository. Every file added to the repository must fall under one
of the categories below. If a new category is needed, this file must be
updated in the same pull request.

| Component                        | Path                                    | License                        |
|----------------------------------|-----------------------------------------|--------------------------------|
| Backend (application code)       | backend/                                | AGPL-3.0 (open source)         |
| Backend (commercial deployments) | backend/                                | Commercial License (see below) |
| CLEAR-D method implementation    | backend/app/discovery/                  | AGPL-3.0 + Commercial          |
| Formal verification (Z3)         | backend/app/verification/               | AGPL-3.0                       |
| Frontend (web application)       | frontend/                               | AGPL-3.0                       |
| SaaS deployment layer            | saas/                                   | Proprietary (Commercial only)  |
| Infrastructure (IaC, deployment) | infrastructure/                         | AGPL-3.0                       |
| Jupyter notebooks (research)     | notebooks/                              | MIT                            |
| Documentation                    | docs/                                   | CC BY-NC 4.0                   |
| Tests                            | backend/tests/, frontend/src/*.test.tsx | AGPL-3.0                       |
| CI/CD configuration              | .github/                                | AGPL-3.0                       |
| Root-level project files         | README, CHANGELOG, CONTRIBUTING, etc.   | CC BY-NC 4.0                   |

NOTES

1. Dual licensing. AeroGrid-XAI is offered under a dual-license model:
   - LICENSE-OPEN-SOURCE (AGPL-3.0) for open-source and academic use.
   - LICENSE-COMMERCIAL for proprietary and commercial use without the
     source-disclosure obligations of the AGPL-3.0.

2. SaaS layer. The multi-tenant SaaS orchestration code in saas/ is
   offered exclusively under the Commercial License. It is not part of
   the AGPL-3.0 distribution.

3. Notebooks. Research notebooks are released under MIT to maximize
   reproducibility and reuse by the scientific community.

4. Documentation. Written specifications, tutorials, and this matrix
   are released under CC BY-NC 4.0 (Attribution, Non-Commercial). To
   use documentation for commercial purposes, a Commercial License is
   required.

5. Contribution. All contributions are governed by CLA.md. Contributors
   retain copyright and grant the Project a sublicensable license
   compatible with both the AGPL-3.0 and the Commercial License.

5a. Future directories. The saas/ and infrastructure/ directories
    referenced above are roadmap deliverables (Sprint 8 and Sprint 11
    respectively) and do not yet exist on disk. Their license rows
    declare the intended terms for when they are created; no code in
    them is currently shipped.

## Maintainer Note on External Legal Review

The roadmap lists "Legal review by external counsel" as a gate for
LICENSE-COMMERCIAL. This review was not performed. The maintainer elected
to defer it on cost grounds. The Commercial License is provided as-is.
If a commercial licensee requires a jurisdiction-specific warranty, that
will be negotiated on a per-license basis at signing time.

This is a documented deviation, not an oversight.
