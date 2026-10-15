# Specification conflicts

This document records every place where the code's cited
specification conflicts with what the repository actually does. It
exists because the specification document itself is **not in the
repository**. Sections and clauses are cited in code comments
(`SPEC §27`, `Section 18`, `Section 35.4`) but there is no
`docs/SPECIFICATION.md` or equivalent on disk. A reader who wants to
check the specification must obtain it externally.

Because the source is not on disk, this document states each
conflict in the form the code actually uses: a citation, the claim
as the code or docs interpret it, and the current state.

---

## SPEC §27 — Research hypotheses

The specification lists twelve research hypotheses (H1-H12). The
authoritative status of each is in `docs/SCIENTIFIC_CLAIMS.md`. Two
conflicts exist between the specification as cited and the current
repository:

### H4 — uncertainty-aware decisions

**Specification claim (as cited in the codebase):** uncertainty-aware
decisions are more robust under environmental variability than point
estimates.

**Repository state:** **FALSIFIED.** `backend/tests/test_h4_uncertainty_decisions.py`
exercises the claim on a declared scope and the claim does not hold.
The platform's Tier 2 interval is constant-width (a single scalar
residual quantile per estimator). An interval-aware policy that
proceeds iff `interval.low >= T` is algebraically identical to a
point policy that proceeds iff `value >= T + q`. At matched proceed
rate there is no room for the claim to hold on this design.

**Resolution:** the specification's H4 statement should be either
(a) withdrawn as a property of the current system, or (b) relabelled
as a research direction that requires a design change (a
per-input interval whose width correlates with the actual error —
group-conditional or Mondrian conformal, or any estimator that
produces a residual quantile as a function of the input rather than
a scalar).

### H7 — hybrid-modality annual availability

**Specification claim (as cited in the codebase):** hybrid
laser+microwave architectures outperform single-modality for annual
availability in most regions.

**Repository state:** **CAPABILITY ABSENT.** The `Hybrid_Link`
modality and its MPE constraint exist and are tested. But the
platform has no annual-availability computation and no regional
aggregation, so the claim cannot be tested at all. See
`docs/H7_AVAILABILITY_SCOPE.md` for the six components that would
have to be built (estimated 6-9 sessions).

**Resolution:** the specification's H7 statement should be
relabelled as a research direction rather than a property claim
about the current system.

---

## What this document is not

- It is not the specification. It cannot be, because the
  specification is not in the repository.
- It is not a claim that the specification is wrong. It is a claim
  that the code has moved past the specification in two specific
  places, and that the specification — when obtained — must be
  reconciled with what the code actually does.
- It is not a substitute for `docs/SCIENTIFIC_CLAIMS.md`. That file
  is the authoritative status of every hypothesis; this file only
  records places where the specification and the repository
  disagree.

---

**Author:** Kian Mansouri Jamshidi
**Date:** 2026-10-16
