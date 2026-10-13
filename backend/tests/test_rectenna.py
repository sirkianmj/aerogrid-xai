"""Tests for the rectenna RF-to-DC conversion efficiency model."""

from __future__ import annotations

import math

import pytest

from app.physics.rectenna import (
    DEFAULT_RECTENNA_CONFIG,
    FREQUENCY_MAX_GHZ,
    FREQUENCY_MIN_GHZ,
    POWER_DENSITY_MAX_W_PER_M2,
    POWER_DENSITY_MIN_W_PER_M2,
    RectennaConfig,
    peak_efficiency_for_frequency,
    rectenna_efficiency,
)

# -- RectennaConfig ----------------------------------------------------------


def test_default_config_values() -> None:
    cfg = RectennaConfig()
    assert cfg.peak_efficiency == 0.82
    assert cfg.peak_input_power_density_w_per_m2 == 1000.0
    assert cfg.reference_frequency_ghz == 5.8
    assert cfg.efficiency_bandwidth_decades == 0.5
    assert cfg.frequency_rolloff_decades == 0.3


def test_config_rejects_nonpositive_peak_efficiency() -> None:
    with pytest.raises(ValueError, match="peak_efficiency"):
        RectennaConfig(peak_efficiency=0.0)


def test_config_rejects_peak_efficiency_above_unity() -> None:
    with pytest.raises(ValueError, match="peak_efficiency"):
        RectennaConfig(peak_efficiency=1.5)


def test_config_rejects_nonpositive_peak_density() -> None:
    with pytest.raises(ValueError, match="peak_input_power_density_w_per_m2"):
        RectennaConfig(peak_input_power_density_w_per_m2=0.0)


def test_config_rejects_nonpositive_reference_frequency() -> None:
    with pytest.raises(ValueError, match="reference_frequency_ghz"):
        RectennaConfig(reference_frequency_ghz=0.0)


def test_config_rejects_nonpositive_bandwidth() -> None:
    with pytest.raises(ValueError, match="efficiency_bandwidth_decades"):
        RectennaConfig(efficiency_bandwidth_decades=0.0)


def test_config_rejects_nonpositive_rolloff() -> None:
    with pytest.raises(ValueError, match="frequency_rolloff_decades"):
        RectennaConfig(frequency_rolloff_decades=0.0)


# -- rectenna_efficiency: peak and direct evaluation ------------------------


def test_efficiency_at_design_point_equals_peak() -> None:
    """At the peak density and reference frequency, efficiency = peak."""
    eta = rectenna_efficiency(
        input_power_density_w_per_m2=1000.0,
        frequency_ghz=5.8,
    )
    assert eta == pytest.approx(0.82, rel=1e-12)


def test_efficiency_direct_evaluation_at_off_peak_point() -> None:
    """Direct evaluation of the Gaussian formula one decade off the
    peak density: eta = peak * exp(-0.5 * (1/0.5)^2)."""
    cfg = RectennaConfig()
    p = 100.0  # 1 decade below the 1000 W/m^2 peak
    expected = cfg.peak_efficiency * math.exp(-0.5 * (1.0 / cfg.efficiency_bandwidth_decades) ** 2)
    eta = rectenna_efficiency(input_power_density_w_per_m2=p, frequency_ghz=5.8)
    assert eta == pytest.approx(expected, rel=1e-12)


def test_efficiency_direct_evaluation_at_off_band_frequency() -> None:
    """Direct evaluation one decade off the reference frequency."""
    cfg = RectennaConfig()
    expected = cfg.peak_efficiency * math.exp(-0.5 * (1.0 / cfg.frequency_rolloff_decades) ** 2)
    eta = rectenna_efficiency(
        input_power_density_w_per_m2=1000.0,
        frequency_ghz=0.58,
    )
    assert eta == pytest.approx(expected, rel=1e-12)


# -- rectenna_efficiency: monotonicity and shape ----------------------------


def test_efficiency_peaks_at_design_density() -> None:
    """Efficiency is highest at the design power density and lower at
    both lower and higher densities."""
    eta_at_peak = rectenna_efficiency(1000.0, 5.8)
    eta_below = rectenna_efficiency(100.0, 5.8)
    eta_above = rectenna_efficiency(10000.0, 5.8)
    assert eta_at_peak > eta_below
    assert eta_at_peak > eta_above


def test_efficiency_decays_symmetrically_in_log10_density() -> None:
    """The Gaussian is symmetric in log10 space: one decade above and
    one decade below the peak give the same efficiency."""
    eta_below = rectenna_efficiency(100.0, 5.8)
    eta_above = rectenna_efficiency(10000.0, 5.8)
    assert eta_below == pytest.approx(eta_above, rel=1e-12)


def test_efficiency_decays_far_from_peak() -> None:
    """Four decades below the peak, the Gaussian has decayed
    dramatically but not necessarily to exactly zero."""
    eta = rectenna_efficiency(0.1, 5.8)
    assert eta < 1e-5


def test_efficiency_is_always_in_bounds() -> None:
    """Efficiency stays in [0, peak_efficiency] over a wide grid."""
    for p in (0.01, 0.1, 1.0, 10.0, 100.0, 1000.0, 10000.0, 1e5, 1e6):
        for f in (0.1, 1.0, 2.45, 5.8, 30.0, 100.0):
            eta = rectenna_efficiency(p, f)
            assert 0.0 <= eta <= DEFAULT_RECTENNA_CONFIG.peak_efficiency, (
                f"eta = {eta} for p={p}, f={f}"
            )


def test_efficiency_at_2_45_ghz_is_lower_than_at_5_8_ghz() -> None:
    """The design frequency is 5.8 GHz, so 2.45 GHz gives lower
    efficiency at the same input power density."""
    eta_58 = rectenna_efficiency(1000.0, 5.8)
    eta_245 = rectenna_efficiency(1000.0, 2.45)
    assert eta_58 > eta_245


# -- rectenna_efficiency: input validation ----------------------------------


def test_efficiency_rejects_nonpositive_density() -> None:
    with pytest.raises(ValueError, match="input_power_density_w_per_m2"):
        rectenna_efficiency(0.0, 5.8)
    with pytest.raises(ValueError, match="input_power_density_w_per_m2"):
        rectenna_efficiency(-1.0, 5.8)


def test_efficiency_rejects_nonpositive_frequency() -> None:
    with pytest.raises(ValueError, match="frequency_ghz"):
        rectenna_efficiency(1000.0, 0.0)
    with pytest.raises(ValueError, match="frequency_ghz"):
        rectenna_efficiency(1000.0, -1.0)


def test_efficiency_rejects_non_finite_inputs() -> None:
    with pytest.raises(ValueError, match="input_power_density_w_per_m2"):
        rectenna_efficiency(float("nan"), 5.8)
    with pytest.raises(ValueError, match="frequency_ghz"):
        rectenna_efficiency(1000.0, float("inf"))


# -- peak_efficiency_for_frequency ------------------------------------------


def test_peak_efficiency_for_reference_frequency_equals_peak() -> None:
    assert peak_efficiency_for_frequency(5.8) == pytest.approx(0.82, rel=1e-12)


def test_peak_efficiency_decreases_away_from_reference() -> None:
    eta_at_ref = peak_efficiency_for_frequency(5.8)
    eta_at_2ghz = peak_efficiency_for_frequency(2.0)
    eta_at_20ghz = peak_efficiency_for_frequency(20.0)
    assert eta_at_ref > eta_at_2ghz
    assert eta_at_ref > eta_at_20ghz


def test_peak_efficiency_rejects_nonpositive_frequency() -> None:
    with pytest.raises(ValueError, match="frequency_ghz"):
        peak_efficiency_for_frequency(0.0)
    with pytest.raises(ValueError, match="frequency_ghz"):
        peak_efficiency_for_frequency(-1.0)


# -- Range of validity -------------------------------------------------------


def test_range_constants_are_in_expected_order() -> None:
    assert DEFAULT_RECTENNA_CONFIG.peak_input_power_density_w_per_m2 > POWER_DENSITY_MIN_W_PER_M2
    assert DEFAULT_RECTENNA_CONFIG.peak_input_power_density_w_per_m2 < POWER_DENSITY_MAX_W_PER_M2
    assert DEFAULT_RECTENNA_CONFIG.reference_frequency_ghz > FREQUENCY_MIN_GHZ
    assert DEFAULT_RECTENNA_CONFIG.reference_frequency_ghz < FREQUENCY_MAX_GHZ


def test_efficiency_at_range_boundaries_is_reasonable() -> None:
    """At the documented range boundaries the model still returns a
    value in bounds; outside it decays smoothly to zero."""
    for p in (POWER_DENSITY_MIN_W_PER_M2, POWER_DENSITY_MAX_W_PER_M2):
        eta = rectenna_efficiency(p, 5.8)
        assert 0.0 <= eta <= 0.82
    for f in (FREQUENCY_MIN_GHZ, FREQUENCY_MAX_GHZ):
        eta = rectenna_efficiency(1000.0, f)
        assert 0.0 <= eta <= 0.82
