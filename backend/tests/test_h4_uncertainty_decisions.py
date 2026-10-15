"""H4: uncertainty-aware decisions are more robust under environmental
variability than point estimates.

Result: FALSIFIED on the platform's current Tier 2 interval design.

The finding
-----------

The platform's Tier 2 interval is *constant-width*:
``AtmosphericSurrogate.calibrate`` (``app/control/tier2.py``) stores a
single scalar residual quantile, so ``estimate_atmospheric_loss``
returns ``[value - q, value + q]`` where ``q`` is the same number for
every input. With that shape, an interval-aware policy that proceeds
iff ``interval.low >= threshold_aware`` is algebraically identical to
a point policy that proceeds iff ``value >= threshold_aware + q``.

At matched proceed rate, the two policies *are the same policy* up to
a threshold shift. There is no room for H4 to hold.

This is not a bug. A single conformal quantile is a valid interval:
it achieves its nominal coverage. But validity is not the same as
*informativeness*. A valid interval can carry no information beyond
its midpoint. H4 requires informativeness; the current design does
not provide it.

What would change the answer
----------------------------

A per-input interval whose width correlates with the actual error.
Group-conditional (Mondrian) conformal, or any scheme that estimates
a residual quantile as a function of the input rather than as a
scalar, would make the interval actionable. This is a design change
to ``AtmosphericSurrogate``, not a test change; it is not applied
here. The SCIENTIFIC_CLAIMS H4 note records it as the required
follow-up.

Scope
-----

- True transmittance per round: log-normal, median 0.5, log-sigma 0.5.
- Constant-width case (matches the platform): value = true + N(0, s_v),
  interval = [value - q, value + q] with q = 0.05 + |N(0, 0.05)|.
- Informative case (contrast): per-round noise scale s drawn from
  |N(0, 0.08)| + 0.02; value = true + N(0, s); interval half = 2s.
- Demand threshold: eta_min = 0.35.
- Post-decision environment: actual = true + N(0, sigma_env).
- Robustness metric: false-proceed rate at matched proceed rate.
- Calibration set 2000, evaluation set 2000.

Does not generalise to arbitrary demand thresholds or true-error
models.
"""

from __future__ import annotations

import math
import random
from collections.abc import Callable

from app.control.tier2 import Tier2Estimate, UncertaintyInterval

N_CALIBRATION = 2000
N_EVALUATION = 2000
BASE_SEED = 20261015

TRUE_MEDIAN = 0.5
TRUE_LOG_SIGMA = 0.5

SIGMA_V = 0.10  # point-estimate error, constant-width case
Q_BASE = 0.05  # constant interval half-width base
Q_SIGMA = 0.05  # constant interval half-width variability

S_INFORM_BASE = 0.02  # informative case: floor on per-round scale
S_INFORM_SIGMA = 0.08  # informative case: per-round scale variability

ETA_MIN = 0.35
NOMINAL_COVERAGE = 0.90


Sample = tuple[Tier2Estimate, float]
ProceedFn = Callable[[Tier2Estimate, float], bool]
Drawer = Callable[[random.Random, float], Sample]


def _clip(x: float, lo: float, hi: float) -> float:
    return min(max(x, lo), hi)


def _sample_true(rng: random.Random) -> float:
    return _clip(TRUE_MEDIAN * math.exp(rng.gauss(0.0, TRUE_LOG_SIGMA)), 0.01, 1.0)


def _make_estimate(value: float, low: float, high: float) -> Tier2Estimate:
    low = min(low, value)
    high = max(high, value)
    return Tier2Estimate(
        value=value,
        interval=UncertaintyInterval(low=low, high=high, nominal_coverage=NOMINAL_COVERAGE),
        model_name="h4_test_synthetic",
    )


def _draw_constant_width(rng: random.Random, sigma_env: float) -> tuple[Tier2Estimate, float]:
    true = _sample_true(rng)
    value = _clip(true + rng.gauss(0.0, SIGMA_V), 0.0, 1.0)
    q = Q_BASE + abs(rng.gauss(0.0, Q_SIGMA))
    est = _make_estimate(value, value - q, value + q)
    actual = _clip(true + rng.gauss(0.0, sigma_env), 0.0, 1.0)
    return est, actual


def _point_proceeds(est: Tier2Estimate, t: float) -> bool:
    return est.value >= t


def _aware_proceeds(est: Tier2Estimate, t: float) -> bool:
    return est.interval.low >= t


def _rate(samples: list[Sample], fn: ProceedFn, t: float) -> float:
    return sum(1 for e, _ in samples if fn(e, t)) / len(samples)


def _bisect_threshold(samples: list[Sample], fn: ProceedFn, target: float) -> float:
    lo, hi = 0.0, 1.0
    for _ in range(40):
        mid = (lo + hi) / 2.0
        if _rate(samples, fn, mid) > target:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2.0


def _false_proceed(samples: list[Sample], fn: ProceedFn, t: float) -> tuple[float, int]:
    n = 0
    f = 0
    for est, actual in samples:
        if fn(est, t):
            n += 1
            if actual < ETA_MIN:
                f += 1
    return (f / n if n else 0.0), n


def _build(drawer: Drawer, sigma_env: float, n: int, seed: int) -> list[Sample]:
    rng = random.Random(seed)
    return [drawer(rng, sigma_env) for _ in range(n)]


def _compare(drawer: Drawer, sigma_env: float, target: float) -> dict[str, float]:
    cal = _build(drawer, sigma_env, N_CALIBRATION, BASE_SEED)
    ev = _build(drawer, sigma_env, N_EVALUATION, BASE_SEED + 1)
    tp = _bisect_threshold(cal, _point_proceeds, target)
    ta = _bisect_threshold(cal, _aware_proceeds, target)
    fp, np_ = _false_proceed(ev, _point_proceeds, tp)
    fa, na = _false_proceed(ev, _aware_proceeds, ta)
    return {
        "t_point": tp,
        "t_aware": ta,
        "fp_point": fp,
        "fp_aware": fa,
        "n_point": float(np_),
        "n_aware": float(na),
    }


def test_matched_proceed_rates_are_close() -> None:
    r = _compare(_draw_constant_width, sigma_env=0.15, target=0.50)
    rel = abs(r["n_point"] - r["n_aware"]) / max(r["n_point"], r["n_aware"], 1.0)
    print(
        f"\n  [H4] matched @ 0.50: n_point={r['n_point']:.0f} "
        f"n_aware={r['n_aware']:.0f}  rel_gap={rel:.3f}"
    )
    assert rel < 0.05


def test_constant_width_aware_equals_shifted_point() -> None:
    """The mechanism diagnosis.

    For a constant-width interval, aware threshold = point threshold
    minus the interval half-width. The empirical half-width is roughly
    Q_BASE, so t_point - t_aware should be close to Q_BASE. If this
    fails, the intervals the test is generating are not constant-width
    and the falsification below is measuring something else.
    """
    r = _compare(_draw_constant_width, sigma_env=0.15, target=0.50)
    observed_shift = r["t_point"] - r["t_aware"]
    print(
        f"\n  [H4] constant-width: t_point={r['t_point']:.4f} "
        f"t_aware={r['t_aware']:.4f}  shift={observed_shift:.4f} "
        f"(Q_BASE={Q_BASE})"
    )
    assert abs(observed_shift - Q_BASE) < 0.05, (
        f"threshold shift {observed_shift:.4f} is not ~Q_BASE "
        f"({Q_BASE}); the intervals may not be constant-width"
    )


def test_h4_falsified_on_constant_width_intervals() -> None:
    """The negative result: aware does not strictly beat point when the
    interval carries no information beyond the midpoint. Both directions
    of the difference are within Monte-Carlo noise.
    """
    r = _compare(_draw_constant_width, sigma_env=0.15, target=0.50)
    gap = r["fp_point"] - r["fp_aware"]
    print(
        f"\n  [H4] constant-width gap at sigma_env=0.15: {gap:+.4f} "
        f"(point={r['fp_point']:.4f}, aware={r['fp_aware']:.4f})"
    )
    assert abs(gap) < 0.01, (
        f"gap {gap:+.4f} outside Monte-Carlo noise band; either the "
        f"model is not constant-width or the diagnosis is wrong"
    )


def test_platform_atmospheric_surrogate_is_constant_width() -> None:
    """Direct structural check on the platform's estimator: its
    interval width is a single scalar for every input.
    """
    import inspect

    from app.control import tier2

    src = inspect.getsource(tier2.AtmosphericSurrogate.calibrate)
    assert "_residual_quantile" in src, "calibrate does not store a scalar quantile"

    src2 = inspect.getsource(tier2.AtmosphericSurrogate.estimate_atmospheric_loss)
    assert "_residual_quantile" in src2, (
        "estimate_atmospheric_loss does not use the scalar quantile"
    )
    print("\n  [H4] platform estimator: interval is a single scalar quantile")
