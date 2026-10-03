# AeroGrid-XAI

A physics-aware, formally verified, interpretable-by-construction Digital
Twin and generative discovery platform for space-to-air wireless energy
transfer and autonomous UAV infrastructure networks.

**Platform:** AeroGrid-XAI
**Method:** CLEAR-D (Coupled-Loop Epistemic Architecture Reasoning and Discovery)

## Status

Pre-release. Sprint 0: repository, legal foundation, and CI/CD.

## Scientific scope

AeroGrid-XAI is a software-only research platform. It does not claim to
build, test, or deploy physical satellites, lasers, UAVs, or power
transmission hardware. It provides the scientific simulation and formal
verification environment required to evaluate candidate architectures
for space-to-air wireless energy transfer under explicitly bounded
physical, thermal, and regulatory constraints.

The epistemic hierarchy enforced throughout the platform distinguishes
seven categories of claim: physical measurement, validated physical
model, estimated model, simulation result, AI prediction, formal
verification result, and hypothetical scenario. Every output artifact
is tagged with its category.

## Licensing

AeroGrid-XAI is distributed under a dual-license model:

- Open Source: GNU Affero General Public License v3.0
  (see LICENSE-OPEN-SOURCE).
- Commercial: a proprietary Commercial License
  (see LICENSE-COMMERCIAL).

The open-source license requires that any derivative work, including
network-hosted services, be released under the same license. If you
wish to use AeroGrid-XAI in a proprietary or closed-source product, or
as a hosted service without source disclosure, you must obtain a
Commercial License.

Component-level license terms are declared in docs/LICENSING_MATRIX.md.

## Defensive publication

The CLEAR-D method, in particular its unsat-core-to-grammar-feature
attribution mechanism for conflict-directed architecture synthesis, is
published here as a defensive publication. No patent has been filed.
The method is prior art as of the first public commit. Anyone may
implement it; attribution to this project is requested but not required
under the AGPL-3.0 terms.

## Contributing

All contributors must sign the Contributor License Agreement
(see CLA.md) before any pull request can be merged. This ensures the
Project retains the rights needed to distribute contributions under
both the open-source and commercial licenses.

## Quick start

mamba env create -f environment.yml
conda activate aerogrid
make test
make dev-backend

## Commercial inquiries

For commercial licensing or partnership:
[contact placeholder - to be set before public release]
