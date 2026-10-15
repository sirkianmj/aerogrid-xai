# H7 — Hybrid-modality availability: scope and gap analysis

**Status:** UNCOVERED, and not closable by a test alone.
**Hypothesis (spec §27):** *Hybrid laser+microwave architectures
outperform single-modality for annual availability in most regions.*

This document exists because H7 is the only remaining UNCOVERED
hypothesis and it cannot be moved to PARTIAL, COVERED, or FALSIFIED by
writing a test. The capability the claim is about does not exist on
the platform. The honest move is to state that, describe what would
need to be built, and let the specification decide whether H7 is a
property claim about the current system or a research direction.

## What the platform currently computes

| Capability | Where | Notes |
|---|---|---|
| Point transmittance at one (site, time, wavelength) | `physics/atmosphere.py::transmission` | Kruse-Kim extinction, Beer-Lambert |
| Single-pass visibility window | `physics/orbital.py::visibility_windows` | Start/end times of one pass |
| Single-point link budget | `physics/link_budget.py::build_physical_link_budget` | Per-link delivered power at one instant |
| Atmospheric transmittance for a mission at one moment | `mission/state.py` | The value displayed in the mission panel |

## What the claim needs

1. **Annual availability**: the fraction of time in a year during
   which a chosen architecture can deliver above some power
   threshold to a chosen region. Requires iterating over at least a
   year of pass geometry with realistic weather.

2. **Regional aggregation**: "most regions" requires a set of
   geographically distributed sites (or a tiling), and each must have
   its own pass geometry and its own weather distribution. A claim
   about "most regions" is a claim about the joint distribution over
   sites.

3. **Hybrid vs single-modality comparison**: two architecture
   families. `Hybrid_Link` exists as a grammar terminal
   (`discovery/grammar.py`) and the encoder emits MPE constraints for
   both mechanisms (`verification/architecture_encoder.py`). A
   single-modality architecture and a hybrid architecture can already
   be constructed and encoded; what cannot be done is evaluating them
   over a year across regions.

4. **Statistical test**: what does "most" mean? A pre-registered
   fraction (e.g. `> 50% of sampled regions`), a confidence interval,
   and a null hypothesis. None of that exists.

## What would have to be built

| Component | Estimated effort | Risk |
|---|---|---|
| Annual pass enumeration for a site | 1 session | Low; Skyfield already does single-pass windows |
| Weather time series model over a year | 2–3 sessions | Medium; the current model is per-slot i.i.d., but a year has temporal correlation |
| Regional site distribution (which regions?) | 1 session, plus a decision | Low technically, but the choice is a scientific design decision |
| Availability metric and threshold | 1 session, plus a decision | Low technically; the choice of threshold is a claim about the mission |
| Hybrid vs single-modality comparison harness | 1 session | Medium; depends on how many architecture variants to test |
| The statistical test itself | 1 session | Low once the above exist |

Roughly **6–9 sessions** for a defensible result. That is not a single
PR.

## What the platform does *not* need to build

- New physics. `Hybrid_Link` produces the correct combined constraint
  set already (`test_encoder_physics.py` covers both mechanisms).
- New grammar. The hybrid architecture is a valid derivation of the
  existing grammar.
- New verification. Z3 feasibility for both modalities is already
  encoded and tested.

## Why this is a scope document, not a test

Every other hypothesis in `SCIENTIFIC_CLAIMS.md` had a mechanism
already present and needed a comparison or a diagnostic. H7 needs a
capability that does not exist. Writing a test that builds a minimal
annual-availability loop *inside the test file* would produce a
number with no bearing on the platform's actual claims, because the
test's loop would not be the loop any real user would run. That is
the anti-pattern: a test that exists to move a row from UNCOVERED to
something else.

## Recommendation

1. Amend SPEC §27 to mark H7 as a **research direction**, not a
   property claim about the current system. It is falsifiable in
   principle, but not by any test that could be written today.
2. If the direction is worth pursuing, split it into the six
   components above and add them to the roadmap with their own
   acceptance criteria.
3. Until then, H7 stays UNCOVERED with this document linked, so
   that no reader mistakes an unbuilt capability for an unverified
   one.

The distinction matters because UNCOVERED normally means "we have the
mechanism, we have not tested it." For H7 it means "we do not have
the mechanism." The SCIENTIFIC_CLAIMS H7 row records that.

---

**Author:** Kian Mansouri Jamshidi
**Date:** 2026-10-15
**Roadmap:** Sprint 13 hypothesis sweep
