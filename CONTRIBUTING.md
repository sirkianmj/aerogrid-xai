# Contributing to AeroGrid-XAI

## Development Setup

1. Install Miniforge (conda-forge).
2. Run: mamba env create -f environment.yml
3. Activate: conda activate aerogrid
4. Run tests: make test

## Pull Request Requirements

Every PR must pass all CI gates:

- Backend: flake8, mypy, pytest with coverage.
- Frontend: lint, test, build.
- Formal verification: Z3 and Lean sanity checks.
- Two-tier invariant: no Tier 2 module reachable from the action interface without passing through Tier 1.

## Scientific Rigor

Any physics, formal-verification, or AI change must cite the specific section of the specification it implements. Do not introduce parameters or constraints without a source.
