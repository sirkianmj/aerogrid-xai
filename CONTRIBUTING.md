# Contributing to AeroGrid-XAI

## Development Setup

1. Install Miniforge (conda-forge).
2. Run: mamba env create -f environment.yml
3. Activate: conda activate aerogrid
4. Run tests: make test

## Pull Request Requirements

Every PR must pass all CI gates:

- Backend: ruff check, ruff format --check, mypy, pytest with coverage.
- Frontend: oxlint, tsc -b, vitest, vite build.
- Formal verification: Z3 sanity check. Z3 is the only formal-verification
  tool used in this project; no Lean.
- CLA: the PR author must be listed in signatures/cla-v1.json.
- Two-tier invariant (Sprint 5): no Tier 2 module reachable from the action
  interface without passing through Tier 1.

## Scientific Rigor

Any physics, formal-verification, or AI change must cite the specific section of the specification it implements. Do not introduce parameters or constraints without a source.

## Contributor License Agreement Enforcement

Every pull request must include a completed signature in the
signatures/ directory before it can be merged. The specific enforcement
mechanism:

1. Contributors append their GitHub username and the date to
   signatures/cla-v1.json as part of their first pull request.
2. A CI job (cla-check) inspects the PR's author against the signature
   file. If the author is not present, the job fails and the PR cannot
   merge.
3. The CLA-assistant GitHub App is optional and may be installed later.
   Until then, the CI job is the enforcement mechanism.

If you are contributing for the first time, add yourself to the
signature file in the same PR.
