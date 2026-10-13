# Scientific validation suite (Sprint 9 s9-2)

Validates the TRL-tagged benchmark table in `app.physics.benchmarks`
against the physics models, within stated error bounds. Complements the
existing unit tests (`test_link_budget.py`, `test_link_budget_gate.py`)
by adding per-source validation modules with explicit error-bound claims
in each assertion.

## Error bounds

- Xidian on-target DC-to-DC 20.8%: reproduced within **5%** relative error.
- Xidian end-to-end wall-plug-to-battery: predicted value must fall in
  the reported **3-5%** band.
- PowerLight delivered ~1 kW at 1,524 m: reproduced within **5%** relative
  error at physically plausible transmitter power.
- DARPA POWER 800 W over 8,600 m: Beer-Lambert transmission coefficient
  at 1,064 nm, clear-air extinction, must be in (0.9, 1.0].
- Han et al. 38.49%: preserved as a **receiver** conversion efficiency,
  not a link efficiency.

## Epistemic categories (specification Section 21)

Every figure in `BENCHMARKS` is a **[PHYSICAL MEASUREMENT]** - a real
hardware test result. The validation suite does not reclassify any of
them. Reproduced quantities computed from physics models are
**[ESTIMATED MODEL]** outputs and are labeled as such in each test's
docstring.

## Sources

Section 6 of `AeroGrid-XAI Final Comprehensive Specification (Rev. 6)`.

## Known limits (carried forward from the specification)

- **P5**: the Han et al. citation lacks a DOI; paper existence is
  unverified. The suite asserts the value is preserved in the table,
  not that the paper is real.
- **Overview Energy** is not a satellite-to-UAV demonstration. The
  validation asserts that the scope note disclaims this; it does not
  attempt a reproduction.
- **DARPA POWER** is a fixed-to-fixed demonstration. The suite asserts
  the transmission coefficient over the stated distance is consistent
  with clear-air 1,064 nm propagation; it does not claim moving-platform
  validation.
