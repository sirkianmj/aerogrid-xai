"""Tests for the Tier 2 atmospheric-loss surrogate.

Roadmap task s5-2: Tier 2 surrogate - atmospheric loss.
Gate: Calibrated 90% CI coverage >= 85% on holdout.
"""

from __future__ import annotations

import math
from itertools import pairwise

import numpy as np
import pytest

from app.control.tier2 import (
    MIN_CALIBRATION_SIZE,
    AtmosphericParams,
    AtmosphericSurrogate,
    Tier2Estimate,
    UncertaintyInterval,
    atmospheric_transmission,
    extinction_coefficient,
)

# -- UncertaintyInterval -----------------------------------------------------


def test_interval_rejects_low_greater_than_high() -> None:
    with pytest.raises(ValueError, match=r"low .* must be <= high"):
        UncertaintyInterval(low=1.0, high=0.5, nominal_coverage=0.9)


def test_interval_rejects_non_finite() -> None:
    with pytest.raises(ValueError, match="must be finite"):
        UncertaintyInterval(low=0.0, high=float("inf"), nominal_coverage=0.9)
    with pytest.raises(ValueError, match="must be finite"):
        UncertaintyInterval(low=float("nan"), high=1.0, nominal_coverage=0.9)


def test_interval_rejects_bad_coverage() -> None:
    with pytest.raises(ValueError, match="nominal_coverage must be in"):
        UncertaintyInterval(low=0.0, high=1.0, nominal_coverage=0.0)
    with pytest.raises(ValueError, match="nominal_coverage must be in"):
        UncertaintyInterval(low=0.0, high=1.0, nominal_coverage=1.0)


def test_interval_contains_and_width() -> None:
    iv = UncertaintyInterval(low=0.2, high=0.8, nominal_coverage=0.9)
    assert iv.contains(0.5)
    assert iv.contains(0.2)
    assert iv.contains(0.8)
    assert not iv.contains(0.1)
    assert iv.width() == pytest.approx(0.6)


# -- Tier2Estimate ----------------------------------------------------------


def test_tier2_estimate_rejects_value_outside_interval() -> None:
    iv = UncertaintyInterval(low=0.2, high=0.8, nominal_coverage=0.9)
    with pytest.raises(ValueError, match="not inside interval"):
        Tier2Estimate(value=0.9, interval=iv, model_name="m")


def test_tier2_estimate_rejects_non_finite_value() -> None:
    iv = UncertaintyInterval(low=0.0, high=1.0, nominal_coverage=0.9)
    with pytest.raises(ValueError, match="value must be finite"):
        Tier2Estimate(value=float("nan"), interval=iv, model_name="m")


def test_tier2_estimate_rejects_empty_model_name() -> None:
    iv = UncertaintyInterval(low=0.0, high=1.0, nominal_coverage=0.9)
    with pytest.raises(ValueError, match="model_name must be non-empty"):
        Tier2Estimate(value=0.5, interval=iv, model_name="")


# -- AtmosphericParams ------------------------------------------------------


def test_params_reject_negative() -> None:
    with pytest.raises(ValueError, match="must be non-negative"):
        AtmosphericParams(A=-1.0)
    with pytest.raises(ValueError, match="must be non-negative"):
        AtmosphericParams(k_cloud=-0.1)


def test_params_reject_non_finite() -> None:
    with pytest.raises(ValueError, match="must be finite"):
        AtmosphericParams(B=float("inf"))


# -- extinction_coefficient and atmospheric_transmission --------------------


def test_extinction_rejects_bad_wavelength() -> None:
    with pytest.raises(ValueError, match="wavelength_nm must be > 0"):
        extinction_coefficient(0.0, 10.0, 0.0, AtmosphericParams())


def test_extinction_rejects_bad_visibility() -> None:
    with pytest.raises(ValueError, match="visibility_km must be > 0"):
        extinction_coefficient(1064.0, 0.0, 0.0, AtmosphericParams())


def test_extinction_rejects_bad_cloud_factor() -> None:
    with pytest.raises(ValueError, match="cloud_factor must be in"):
        extinction_coefficient(1064.0, 10.0, 1.5, AtmosphericParams())
    with pytest.raises(ValueError, match="cloud_factor must be in"):
        extinction_coefficient(1064.0, 10.0, -0.1, AtmosphericParams())


def test_transmission_zero_path_is_one() -> None:
    tau = atmospheric_transmission(1064.0, 0.0, 10.0, 0.0, AtmosphericParams())
    assert tau == pytest.approx(1.0)


def test_transmission_rejects_negative_path() -> None:
    with pytest.raises(ValueError, match="path_m must be >= 0"):
        atmospheric_transmission(1064.0, -1.0, 10.0, 0.0, AtmosphericParams())


def test_transmission_monotone_decreasing_in_path() -> None:
    p = AtmosphericParams()
    taus = [
        atmospheric_transmission(1064.0, L, 10.0, 0.2, p)
        for L in (0.0, 500.0, 1000.0, 2000.0, 5000.0)
    ]
    for a, b in pairwise(taus):
        assert a > b


def test_transmission_decreases_with_cloud() -> None:
    p = AtmosphericParams()
    t_clear = atmospheric_transmission(1064.0, 1000.0, 20.0, 0.0, p)
    t_cloudy = atmospheric_transmission(1064.0, 1000.0, 20.0, 0.8, p)
    assert t_clear > t_cloudy


# -- Surrogate state --------------------------------------------------------


def test_surrogate_is_uncalibrated_initially() -> None:
    s = AtmosphericSurrogate()
    assert not s.is_calibrated
    assert s.calibration_size == 0


def test_surrogate_raises_before_calibration() -> None:
    s = AtmosphericSurrogate()
    with pytest.raises(RuntimeError, match="before calibrate"):
        s.estimate_atmospheric_loss(
            {
                "wavelength_nm": 1064.0,
                "path_m": 1000.0,
                "visibility_km": 10.0,
                "cloud_factor": 0.0,
            }
        )


def test_surrogate_calibration_rejects_mismatched_lengths() -> None:
    s = AtmosphericSurrogate()
    with pytest.raises(ValueError, match="same length"):
        s.calibrate(
            calibration_inputs=[{}] * 20,
            calibration_targets=[0.5] * 10,
        )


def test_surrogate_calibration_rejects_too_small_set() -> None:
    s = AtmosphericSurrogate()
    with pytest.raises(ValueError, match="at least"):
        s.calibrate(
            calibration_inputs=[{}] * (MIN_CALIBRATION_SIZE - 1),
            calibration_targets=[0.5] * (MIN_CALIBRATION_SIZE - 1),
        )


def test_surrogate_calibration_rejects_bad_coverage() -> None:
    s = AtmosphericSurrogate()
    with pytest.raises(ValueError, match="nominal_coverage must be in"):
        s.calibrate(
            calibration_inputs=[{}] * 20,
            calibration_targets=[0.5] * 20,
            nominal_coverage=1.5,
        )


def test_surrogate_calibration_rejects_non_finite_target() -> None:
    s = AtmosphericSurrogate()
    with pytest.raises(ValueError, match="not finite"):
        s.calibrate(
            calibration_inputs=[{}] * 20,
            calibration_targets=[float("nan")] + [0.5] * 19,
        )


def test_surrogate_estimate_rejects_missing_key() -> None:
    s = AtmosphericSurrogate()
    s.calibrate(
        calibration_inputs=[
            {
                "wavelength_nm": 1064.0,
                "path_m": 100.0,
                "visibility_km": 10.0,
                "cloud_factor": 0.0,
            }
        ]
        * 20,
        calibration_targets=[0.9] * 20,
    )
    with pytest.raises(ValueError, match="missing input key"):
        s.estimate_atmospheric_loss({"wavelength_nm": 1064.0})


# -- Determinism ------------------------------------------------------------


def test_surrogate_estimate_is_deterministic() -> None:
    s = AtmosphericSurrogate()
    inputs_cal = [
        {
            "wavelength_nm": 1064.0,
            "path_m": 100.0 * i,
            "visibility_km": 10.0,
            "cloud_factor": 0.0,
        }
        for i in range(20)
    ]
    targets_cal = [0.9] * 20
    s.calibrate(inputs_cal, targets_cal, nominal_coverage=0.9)
    inp = {
        "wavelength_nm": 1064.0,
        "path_m": 500.0,
        "visibility_km": 10.0,
        "cloud_factor": 0.2,
    }
    e1 = s.estimate_atmospheric_loss(inp)
    e2 = s.estimate_atmospheric_loss(inp)
    assert e1 == e2


# -- Gate: coverage on holdout ----------------------------------------------


def _sample_inputs(rng: np.random.Generator, n: int) -> list[dict[str, float]]:
    return [
        {
            "wavelength_nm": float(rng.choice([520.0, 1064.0])),
            "path_m": float(rng.uniform(100.0, 5000.0)),
            "visibility_km": float(rng.uniform(5.0, 50.0)),
            "cloud_factor": float(rng.uniform(0.0, 0.8)),
        }
        for _ in range(n)
    ]


def _true_targets(rng: np.random.Generator, inputs: list[dict[str, float]]) -> list[float]:
    """Ground-truth transmission under a *different* model than the
    surrogate: the same additive form with a 15 percent multiplicative
    bias on the extinction coefficient, plus Gaussian measurement
    noise. The surrogate is therefore systematically wrong, which is
    exactly the regime split conformal is designed for: the coverage
    guarantee holds regardless of base-model correctness."""
    targets: list[float] = []
    params_true = AtmosphericParams()
    for inp in inputs:
        alpha = extinction_coefficient(
            wavelength_nm=inp["wavelength_nm"],
            visibility_km=inp["visibility_km"],
            cloud_factor=inp["cloud_factor"],
            params=params_true,
        )
        alpha_biased = alpha * 1.15
        tau = math.exp(-alpha_biased * inp["path_m"])
        noise = rng.normal(0.0, 0.005)
        targets.append(min(1.0, max(0.0, tau + noise)))
    return targets


def test_gate_90pct_coverage_at_least_85pct() -> None:
    """The s5-2 gate: 90 percent CI coverage on holdout >= 85 percent."""
    rng = np.random.default_rng(20261009)
    inputs_cal = _sample_inputs(rng, 500)
    targets_cal = _true_targets(rng, inputs_cal)
    inputs_test = _sample_inputs(rng, 200)
    targets_test = _true_targets(rng, inputs_test)

    surrogate = AtmosphericSurrogate()
    surrogate.calibrate(inputs_cal, targets_cal, nominal_coverage=0.90)

    covered = 0
    for inp, tgt in zip(inputs_test, targets_test, strict=True):
        est = surrogate.estimate_atmospheric_loss(inp)
        if est.interval.contains(tgt):
            covered += 1
    coverage = covered / len(inputs_test)
    print(f"Holdout coverage: {coverage:.3f} (nominal 0.90, gate 0.85)")
    assert coverage >= 0.85, f"Holdout coverage {coverage:.3f} below gate 0.85"


def test_average_coverage_over_many_seeds_at_least_88pct() -> None:
    """Stronger check: over 20 independent calibration/holdout splits,
    the mean empirical coverage should be close to nominal."""
    coverages: list[float] = []
    for seed in range(20):
        rng = np.random.default_rng(seed)
        inputs_cal = _sample_inputs(rng, 300)
        targets_cal = _true_targets(rng, inputs_cal)
        inputs_test = _sample_inputs(rng, 150)
        targets_test = _true_targets(rng, inputs_test)

        surrogate = AtmosphericSurrogate()
        surrogate.calibrate(inputs_cal, targets_cal, nominal_coverage=0.90)

        covered = sum(
            1
            for inp, tgt in zip(inputs_test, targets_test, strict=True)
            if surrogate.estimate_atmospheric_loss(inp).interval.contains(tgt)
        )
        coverages.append(covered / len(inputs_test))

    mean_coverage = sum(coverages) / len(coverages)
    print(
        f"Mean coverage over 20 seeds: {mean_coverage:.3f} "
        f"(min {min(coverages):.3f}, max {max(coverages):.3f})"
    )
    assert mean_coverage >= 0.88, f"Mean coverage {mean_coverage:.3f} below 0.88"


def test_interval_widths_shrink_with_larger_calibration() -> None:
    """A larger calibration set tightens the conformal quantile.
    This is not required by the gate but is a sanity property."""
    rng = np.random.default_rng(42)
    inputs_small = _sample_inputs(rng, 30)
    targets_small = _true_targets(rng, inputs_small)
    inputs_large = _sample_inputs(rng, 2000)
    targets_large = _true_targets(rng, inputs_large)

    s_small = AtmosphericSurrogate()
    s_small.calibrate(inputs_small, targets_small, nominal_coverage=0.9)
    s_large = AtmosphericSurrogate()
    s_large.calibrate(inputs_large, targets_large, nominal_coverage=0.9)

    test_inp = {
        "wavelength_nm": 1064.0,
        "path_m": 1000.0,
        "visibility_km": 15.0,
        "cloud_factor": 0.2,
    }
    w_small = s_small.estimate_atmospheric_loss(test_inp).interval.width()
    w_large = s_large.estimate_atmospheric_loss(test_inp).interval.width()
    assert w_large <= w_small
