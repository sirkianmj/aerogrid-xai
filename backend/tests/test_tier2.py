"""Tests for the Tier 2 atmospheric-loss surrogate.

Roadmap task s5-2: Tier 2 surrogate - atmospheric loss.
Gate: Calibrated 90% CI coverage >= 85% on holdout.
"""

from __future__ import annotations

import numpy as np
import pytest

from app.control.tier2 import (
    MIN_CALIBRATION_SIZE,
    AtmosphericSurrogate,
    Tier2Estimate,
    UncertaintyInterval,
)
from app.physics.atmosphere import AtmosphereConfig
from app.physics.atmosphere import transmission as atmospheric_transmission

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
    """Ground-truth transmission under a systematically-biased version
    of the surrogate's point model.

    The surrogate uses physics.atmosphere.transmission with the default
    AtmosphereConfig. The ground truth here uses the same model but
    raises the transmission to the 1.15 power, which is equivalent to
    biasing the extinction coefficient by 15 percent (tau^1.15 =
    exp(-1.15 * alpha * L)). The surrogate is therefore systematically
    wrong, which is exactly the regime split conformal is designed for:
    the coverage guarantee holds regardless of base-model correctness.

    A small Gaussian measurement noise term is added on top so the
    residuals are not purely the systematic bias."""
    targets: list[float] = []
    for inp in inputs:
        tau_base = atmospheric_transmission(
            wavelength_nm=inp["wavelength_nm"],
            path_length_m=inp["path_m"],
            visibility_km=inp["visibility_km"],
            cloud_factor=inp["cloud_factor"],
        )
        tau_biased = tau_base**1.15
        noise = rng.normal(0.0, 0.005)
        targets.append(min(1.0, max(0.0, tau_biased + noise)))
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


# -- Config plumbing --------------------------------------------------------


def test_surrogate_accepts_atmosphere_config() -> None:
    """The surrogate honours a non-default AtmosphereConfig."""
    config_dry = AtmosphereConfig(molecular_extinction_per_km=1e-6)
    config_wet = AtmosphereConfig(molecular_extinction_per_km=1.0)
    s_dry = AtmosphericSurrogate(config=config_dry)
    s_wet = AtmosphericSurrogate(config=config_wet)
    inp = {
        "wavelength_nm": 1064.0,
        "path_m": 1000.0,
        "visibility_km": 20.0,
        "cloud_factor": 0.0,
    }
    tau_dry = s_dry._predict(inp)
    tau_wet = s_wet._predict(inp)
    assert tau_wet < tau_dry


def test_surrogate_default_config_matches_physics_default() -> None:
    """With no config argument, _predict uses AtmosphereConfig()'s defaults."""
    s = AtmosphericSurrogate()
    inp = {
        "wavelength_nm": 1064.0,
        "path_m": 1000.0,
        "visibility_km": 20.0,
        "cloud_factor": 0.0,
    }
    expected = atmospheric_transmission(
        wavelength_nm=1064.0,
        path_length_m=1000.0,
        visibility_km=20.0,
        cloud_factor=0.0,
    )
    assert s._predict(inp) == pytest.approx(expected, rel=1e-12)
