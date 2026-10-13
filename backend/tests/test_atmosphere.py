"""Tests for the atmospheric extinction and transmittance model."""

from __future__ import annotations

import math
from itertools import pairwise

import pytest

from app.physics.atmosphere import (
    DEFAULT_ATMOSPHERE_CONFIG,
    VISIBILITY_MAX_KM,
    VISIBILITY_MIN_KM,
    WAVELENGTH_MAX_NM,
    WAVELENGTH_MIN_NM,
    AtmosphereConfig,
    aerosol_extinction_per_km,
    cloud_extinction_per_km,
    kruse_q_exponent,
    molecular_extinction_per_km,
    total_extinction_per_km,
    transmission,
    transmission_db,
)

# -- kruse_q_exponent ---------------------------------------------------------


def test_kruse_q_clear_visibility() -> None:
    """V > 50 km: q = 1.6 (Kruse 1962 high-visibility branch)."""
    assert kruse_q_exponent(100.0) == 1.6
    assert kruse_q_exponent(50.1) == 1.6


def test_kruse_q_mid_visibility() -> None:
    """6 < V <= 50 km: q = 1.3 (Kruse 1962 mid-visibility branch)."""
    assert kruse_q_exponent(50.0) == 1.3
    assert kruse_q_exponent(10.0) == 1.3
    assert kruse_q_exponent(6.1) == 1.3


def test_kruse_q_low_visibility_kim() -> None:
    """Kim 2001 refinement: 1 < V <= 6 km -> q = 0.16 V + 0.34."""
    q = kruse_q_exponent(5.0)
    assert q == pytest.approx(0.16 * 5.0 + 0.34)
    q = kruse_q_exponent(2.0)
    assert q == pytest.approx(0.16 * 2.0 + 0.34)


def test_kruse_q_very_low_visibility_kim() -> None:
    """Kim 2001: 0.5 < V <= 1 km -> q = V - 0.5."""
    assert kruse_q_exponent(1.0) == pytest.approx(0.5)
    assert kruse_q_exponent(0.75) == pytest.approx(0.25)


def test_kruse_q_dense_fog_kim() -> None:
    """Kim 2001: V <= 0.5 km -> q = 0."""
    assert kruse_q_exponent(0.5) == 0.0
    assert kruse_q_exponent(0.1) == 0.0


def test_kruse_q_kruse_original_low_visibility() -> None:
    """use_kim=False uses Kruse 1962 q = 0.585 * V ** (1/3)."""
    expected = 0.585 * (2.0 ** (1.0 / 3.0))
    assert kruse_q_exponent(2.0, use_kim=False) == pytest.approx(expected)


def test_kruse_q_rejects_nonpositive_visibility() -> None:
    with pytest.raises(ValueError, match="visibility_km"):
        kruse_q_exponent(0.0)
    with pytest.raises(ValueError, match="visibility_km"):
        kruse_q_exponent(-1.0)


# -- aerosol_extinction_per_km ------------------------------------------------


def test_aerosol_extinction_reproduces_kruse_formula() -> None:
    """Direct evaluation of the Kruse-Kim formula at a known point."""
    wavelength_nm = 1064.0
    visibility_km = 20.0
    expected_q = 1.3
    expected = (3.91 / visibility_km) * ((wavelength_nm / 1000.0) / 0.55) ** (-expected_q)
    result = aerosol_extinction_per_km(wavelength_nm, visibility_km)
    assert result == pytest.approx(expected, rel=1e-12)


def test_aerosol_extinction_decreases_with_visibility() -> None:
    """Lower extinction as visibility increases."""
    values = [aerosol_extinction_per_km(1064.0, v) for v in (1.0, 5.0, 20.0, 80.0)]
    for a, b in pairwise(values):
        assert a > b, f"not monotonically decreasing: {values}"


def test_aerosol_extinction_wavelength_dependence_clear_air() -> None:
    """In clear air (q = 1.3), longer wavelengths penetrate better."""
    alpha_520 = aerosol_extinction_per_km(520.0, 20.0)
    alpha_1064 = aerosol_extinction_per_km(1064.0, 20.0)
    alpha_1550 = aerosol_extinction_per_km(1550.0, 20.0)
    assert alpha_520 > alpha_1064 > alpha_1550


def test_aerosol_extinction_rejects_nonpositive_wavelength() -> None:
    with pytest.raises(ValueError, match="wavelength_nm"):
        aerosol_extinction_per_km(0.0, 20.0)
    with pytest.raises(ValueError, match="wavelength_nm"):
        aerosol_extinction_per_km(-100.0, 20.0)


def test_aerosol_extinction_rejects_nonpositive_visibility() -> None:
    with pytest.raises(ValueError, match="visibility_km"):
        aerosol_extinction_per_km(1064.0, 0.0)
    with pytest.raises(ValueError, match="visibility_km"):
        aerosol_extinction_per_km(1064.0, -1.0)


# -- molecular_extinction_per_km ----------------------------------------------


def test_molecular_extinction_returns_config_value() -> None:
    cfg = AtmosphereConfig(molecular_extinction_per_km=0.05)
    assert molecular_extinction_per_km(cfg) == 0.05


def test_molecular_extinction_default_is_positive() -> None:
    assert molecular_extinction_per_km() > 0.0


# -- cloud_extinction_per_km --------------------------------------------------


def test_cloud_extinction_zero_for_clear_sky() -> None:
    assert cloud_extinction_per_km(0.0) == 0.0


def test_cloud_extinction_linear_in_cloud_factor() -> None:
    cfg = AtmosphereConfig(cloud_extinction_per_km_per_unit_cover=2.0)
    assert cloud_extinction_per_km(1.0, cfg) == 2.0
    assert cloud_extinction_per_km(0.5, cfg) == 1.0
    assert cloud_extinction_per_km(0.1, cfg) == pytest.approx(0.2)


def test_cloud_extinction_rejects_out_of_range_cloud_factor() -> None:
    with pytest.raises(ValueError, match="cloud_factor"):
        cloud_extinction_per_km(-0.1)
    with pytest.raises(ValueError, match="cloud_factor"):
        cloud_extinction_per_km(1.1)


# -- total_extinction_per_km --------------------------------------------------


def test_total_extinction_is_sum_of_components() -> None:
    cfg = AtmosphereConfig(molecular_extinction_per_km=0.01, use_kim_refinement=True)
    total = total_extinction_per_km(1064.0, 20.0, 0.3, cfg)
    mol = molecular_extinction_per_km(cfg)
    aer = aerosol_extinction_per_km(1064.0, 20.0, use_kim=True)
    cld = cloud_extinction_per_km(0.3, cfg)
    assert total == pytest.approx(mol + aer + cld, rel=1e-12)


def test_total_extinction_rejects_out_of_range_wavelength() -> None:
    with pytest.raises(ValueError, match="wavelength_nm"):
        total_extinction_per_km(WAVELENGTH_MIN_NM - 1.0, 20.0, 0.0)
    with pytest.raises(ValueError, match="wavelength_nm"):
        total_extinction_per_km(WAVELENGTH_MAX_NM + 1.0, 20.0, 0.0)


def test_total_extinction_rejects_out_of_range_visibility() -> None:
    with pytest.raises(ValueError, match="visibility_km"):
        total_extinction_per_km(1064.0, VISIBILITY_MIN_KM - 0.01, 0.0)
    with pytest.raises(ValueError, match="visibility_km"):
        total_extinction_per_km(1064.0, VISIBILITY_MAX_KM + 1.0, 0.0)


# -- transmission -------------------------------------------------------------


def test_transmission_at_zero_path_is_unity() -> None:
    assert transmission(1064.0, 0.0, 20.0, 0.0) == 1.0


def test_transmission_decreases_with_path_length() -> None:
    values = [
        transmission(1064.0, length_m, 20.0, 0.0) for length_m in (0.0, 1000.0, 5000.0, 20000.0)
    ]
    for a, b in pairwise(values):
        assert a > b, f"not monotonically decreasing: {values}"


def test_transmission_rejects_negative_path() -> None:
    with pytest.raises(ValueError, match="path_length_m"):
        transmission(1064.0, -1.0, 20.0, 0.0)


def test_transmission_matches_beer_lambert_from_extinction() -> None:
    cfg = AtmosphereConfig(molecular_extinction_per_km=0.02)
    alpha_per_km = total_extinction_per_km(1064.0, 20.0, 0.2, cfg)
    tau = transmission(1064.0, 5000.0, 20.0, 0.2, cfg)
    expected = math.exp(-alpha_per_km / 1000.0 * 5000.0)
    assert tau == pytest.approx(expected, rel=1e-12)


def test_transmission_within_unit_interval() -> None:
    # At extreme optical depth (dense fog over tens of km) the
    # exponential underflows to 0.0 in double precision. That is the
    # physically meaningful limit, so the assertion allows 0.0.
    for length_m in (0.0, 100.0, 1000.0, 10000.0, 100000.0):
        for visibility_km in (0.1, 1.0, 10.0, 50.0):
            for c in (0.0, 0.5, 1.0):
                tau = transmission(1064.0, length_m, visibility_km, c)
                assert 0.0 <= tau <= 1.0, (
                    f"tau = {tau} for length_m={length_m} visibility_km={visibility_km} c={c}"
                )


# -- transmission_db ----------------------------------------------------------


def test_transmission_db_zero_at_zero_path() -> None:
    assert transmission_db(1064.0, 0.0, 20.0, 0.0) == 0.0


def test_transmission_db_is_negative_for_finite_path() -> None:
    db = transmission_db(1064.0, 5000.0, 20.0, 0.0)
    assert db < 0.0


def test_transmission_db_is_10_log10_of_tau() -> None:
    tau = transmission(1064.0, 5000.0, 20.0, 0.0)
    db = transmission_db(1064.0, 5000.0, 20.0, 0.0)
    assert db == pytest.approx(10.0 * math.log10(tau), rel=1e-12)


# -- AtmosphereConfig ---------------------------------------------------------


def test_config_defaults_are_positive() -> None:
    cfg = AtmosphereConfig()
    assert cfg.molecular_extinction_per_km >= 0.0
    assert cfg.cloud_extinction_per_km_per_unit_cover >= 0.0


def test_config_rejects_negative_molecular() -> None:
    with pytest.raises(ValueError, match="molecular_extinction_per_km"):
        AtmosphereConfig(molecular_extinction_per_km=-1e-4)


def test_config_rejects_negative_cloud_coefficient() -> None:
    with pytest.raises(ValueError, match="cloud_extinction_per_km_per_unit_cover"):
        AtmosphereConfig(cloud_extinction_per_km_per_unit_cover=-1.0)


def test_default_config_uses_kim_refinement() -> None:
    assert DEFAULT_ATMOSPHERE_CONFIG.use_kim_refinement is True
