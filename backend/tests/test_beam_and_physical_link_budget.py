"""Tests for Gaussian beam geometry and physical link budget."""

from __future__ import annotations

import math
from itertools import pairwise

import pytest

from app.physics.atmosphere import AtmosphereConfig
from app.physics.beam import (
    BeamParams,
    beam_radius_m,
    combined_beam_efficiency,
    far_field_divergence_rad,
    pointing_efficiency,
    rayleigh_range_m,
    spillover_efficiency,
)
from app.physics.link_budget import (
    LinkBudget,
    build_canonical_link_budget,
    build_physical_link_budget,
)

# -- rayleigh_range_m ---------------------------------------------------------


def test_rayleigh_range_matches_formula() -> None:
    """z_R = pi * w0^2 / lambda. Direct evaluation at a known point."""
    wavelength_nm = 1064.0
    w0 = 0.02
    expected = math.pi * w0 * w0 / (wavelength_nm * 1e-9)
    assert rayleigh_range_m(wavelength_nm, w0) == pytest.approx(expected, rel=1e-12)


def test_rayleigh_range_scales_with_waist_squared() -> None:
    z1 = rayleigh_range_m(1064.0, 0.01)
    z2 = rayleigh_range_m(1064.0, 0.02)
    assert z2 / z1 == pytest.approx(4.0, rel=1e-12)


def test_rayleigh_range_rejects_nonpositive_inputs() -> None:
    with pytest.raises(ValueError, match="wavelength_nm"):
        rayleigh_range_m(0.0, 0.02)
    with pytest.raises(ValueError, match="waist_radius_m"):
        rayleigh_range_m(1064.0, 0.0)


# -- beam_radius_m ------------------------------------------------------------


def test_beam_radius_at_waist_equals_w0() -> None:
    assert beam_radius_m(1064.0, 0.02, 0.0) == pytest.approx(0.02, rel=1e-12)


def test_beam_radius_at_rayleigh_range_sqrt2_w0() -> None:
    """At z = z_R the beam radius is sqrt(2) * w0."""
    w0 = 0.02
    z_r = rayleigh_range_m(1064.0, w0)
    w_at_zr = beam_radius_m(1064.0, w0, z_r)
    assert w_at_zr == pytest.approx(math.sqrt(2.0) * w0, rel=1e-9)


def test_beam_radius_monotonic_in_range() -> None:
    ranges = (0.0, 1.0, 10.0, 100.0, 1000.0)
    values = [beam_radius_m(1064.0, 0.02, z) for z in ranges]
    for a, b in pairwise(values):
        assert b > a


def test_beam_radius_rejects_negative_range() -> None:
    with pytest.raises(ValueError, match="range_m"):
        beam_radius_m(1064.0, 0.02, -1.0)


# -- far_field_divergence_rad -------------------------------------------------


def test_far_field_divergence_matches_formula() -> None:
    expected = (1064.0 * 1e-9) / (math.pi * 0.02)
    assert far_field_divergence_rad(1064.0, 0.02) == pytest.approx(expected, rel=1e-12)


def test_far_field_divergence_smaller_for_bigger_waist() -> None:
    theta_small = far_field_divergence_rad(1064.0, 0.005)
    theta_large = far_field_divergence_rad(1064.0, 0.05)
    assert theta_large < theta_small


# -- spillover_efficiency -----------------------------------------------------


def test_spillover_large_aperture_approaches_unity() -> None:
    """a >> w: nearly all beam power is captured."""
    eta = spillover_efficiency(beam_radius_m=0.01, receiver_radius_m=1.0)
    assert eta > 0.9999


def test_spillover_small_aperture_small_fraction() -> None:
    """a << w: only a small fraction of beam power is captured."""
    eta = spillover_efficiency(beam_radius_m=1.0, receiver_radius_m=0.01)
    assert eta < 0.001


def test_spillover_formula_direct_evaluation() -> None:
    """eta = 1 - exp(-2 * a^2 / w^2)."""
    w = 0.5
    a = 0.3
    expected = 1.0 - math.exp(-2.0 * a * a / (w * w))
    assert spillover_efficiency(w, a) == pytest.approx(expected, rel=1e-12)


def test_spillover_rejects_nonpositive_inputs() -> None:
    with pytest.raises(ValueError, match="beam_radius_m"):
        spillover_efficiency(0.0, 0.5)
    with pytest.raises(ValueError, match="receiver_radius_m"):
        spillover_efficiency(0.5, 0.0)


# -- pointing_efficiency ------------------------------------------------------


def test_pointing_zero_offset_is_unity() -> None:
    assert pointing_efficiency(0.0, 0.5) == 1.0


def test_pointing_formula_direct_evaluation() -> None:
    """eta = exp(-2 * delta^2 / w^2)."""
    w = 0.5
    delta = 0.1
    expected = math.exp(-2.0 * delta * delta / (w * w))
    assert pointing_efficiency(delta, w) == pytest.approx(expected, rel=1e-12)


def test_pointing_monotonic_decreasing_in_offset() -> None:
    offsets = (0.0, 0.05, 0.1, 0.2, 0.5)
    values = [pointing_efficiency(d, 0.5) for d in offsets]
    for a, b in pairwise(values):
        assert b < a


def test_pointing_rejects_negative_offset() -> None:
    with pytest.raises(ValueError, match="offset_m"):
        pointing_efficiency(-0.1, 0.5)


# -- combined_beam_efficiency -------------------------------------------------


def test_combined_is_product_of_components() -> None:
    w = 0.5
    a = 0.3
    d = 0.1
    expected = spillover_efficiency(w, a) * pointing_efficiency(d, w)
    assert combined_beam_efficiency(w, a, d) == pytest.approx(expected, rel=1e-12)


def test_combined_bounded_in_unit_interval() -> None:
    # At extreme offset-to-beam-radius ratios the pointing term
    # exp(-2 * delta^2 / w^2) underflows to 0.0 in IEEE 754 double
    # precision. 0.0 is the physically meaningful limit: a receiver
    # tens of beam radii off-axis captures no measurable power.
    for w in (0.01, 0.1, 1.0, 10.0):
        for a in (0.01, 0.1, 1.0):
            for d in (0.0, 0.05, 0.5):
                eta = combined_beam_efficiency(w, a, d)
                assert 0.0 <= eta <= 1.0


# -- BeamParams ---------------------------------------------------------------


def test_beam_params_defaults_are_valid() -> None:
    p = BeamParams()
    assert p.wavelength_nm > 0.0
    assert p.waist_radius_m > 0.0
    assert 0.0 < p.transmitter_efficiency <= 1.0


def test_beam_params_rejects_nonpositive_wavelength() -> None:
    with pytest.raises(ValueError, match="wavelength_nm"):
        BeamParams(wavelength_nm=0.0)


def test_beam_params_rejects_out_of_range_transmitter_efficiency() -> None:
    with pytest.raises(ValueError, match="transmitter_efficiency"):
        BeamParams(transmitter_efficiency=0.0)
    with pytest.raises(ValueError, match="transmitter_efficiency"):
        BeamParams(transmitter_efficiency=1.5)


# -- build_physical_link_budget -----------------------------------------------


def _build(
    input_power_w: float = 1000.0,
    wavelength_nm: float = 1064.0,
    waist_radius_m: float = 0.02,
    transmitter_efficiency: float = 0.30,
    range_m: float = 5000.0,
    receiver_aperture_radius_m: float = 0.3,
    pointing_offset_m: float = 0.0,
    visibility_km: float = 20.0,
    cloud_factor: float = 0.0,
    receiver_conversion_efficiency: float = 0.20,
    battery_efficiency: float = 0.92,
    atmosphere_config: AtmosphereConfig | None = None,
) -> LinkBudget:
    """Typed wrapper around build_physical_link_budget with defaults.

    Uses explicit named parameters rather than a dict splat so that
    mypy can verify the argument types against the function signature.
    """
    return build_physical_link_budget(
        input_power_w=input_power_w,
        wavelength_nm=wavelength_nm,
        waist_radius_m=waist_radius_m,
        transmitter_efficiency=transmitter_efficiency,
        range_m=range_m,
        receiver_aperture_radius_m=receiver_aperture_radius_m,
        pointing_offset_m=pointing_offset_m,
        visibility_km=visibility_km,
        cloud_factor=cloud_factor,
        receiver_conversion_efficiency=receiver_conversion_efficiency,
        battery_efficiency=battery_efficiency,
        atmosphere_config=atmosphere_config,
    )


def test_physical_link_budget_has_four_canonical_stages() -> None:
    lb = _build()
    assert isinstance(lb, LinkBudget)
    names = tuple(s.name for s in lb.stages)
    assert names == ("transmitter", "beam", "receiver", "battery")


def test_physical_link_budget_end_to_end_is_product_of_stages() -> None:
    lb = _build()
    product = 1.0
    for s in lb.stages:
        product *= s.efficiency
    assert lb.end_to_end_efficiency == pytest.approx(product, rel=1e-12)


def test_physical_link_budget_end_to_end_below_each_stage() -> None:
    """End-to-end efficiency is strictly below every individual stage."""
    lb = _build()
    e2e = lb.end_to_end_efficiency
    for s in lb.stages:
        if s.efficiency < 1.0:
            assert e2e < s.efficiency


def test_physical_link_budget_output_is_input_times_efficiency() -> None:
    lb = _build()
    assert lb.output_power_w == pytest.approx(
        lb.input_power_w * lb.end_to_end_efficiency, rel=1e-12
    )


def test_physical_link_budget_beam_stage_decreases_with_range() -> None:
    near = _build(range_m=1000.0)
    far = _build(range_m=20000.0)
    beam_near = next(s.efficiency for s in near.stages if s.name == "beam")
    beam_far = next(s.efficiency for s in far.stages if s.name == "beam")
    assert beam_far < beam_near


def test_physical_link_budget_beam_stage_decreases_with_cloud() -> None:
    clear = _build(cloud_factor=0.0)
    cloudy = _build(cloud_factor=0.8)
    beam_clear = next(s.efficiency for s in clear.stages if s.name == "beam")
    beam_cloudy = next(s.efficiency for s in cloudy.stages if s.name == "beam")
    assert beam_cloudy < beam_clear


def test_physical_link_budget_rejects_nonpositive_input_power() -> None:
    with pytest.raises(ValueError, match="input_power_w"):
        _build(input_power_w=0.0)


def test_physical_link_budget_rejects_bad_transmitter_efficiency() -> None:
    with pytest.raises(ValueError, match="transmitter_efficiency"):
        _build(transmitter_efficiency=0.0)


def test_physical_link_budget_rejects_bad_battery_efficiency() -> None:
    with pytest.raises(ValueError, match="battery_efficiency"):
        _build(battery_efficiency=0.0)


def test_physical_link_budget_rejects_bad_receiver_efficiency() -> None:
    with pytest.raises(ValueError, match="receiver_conversion_efficiency"):
        _build(receiver_conversion_efficiency=0.0)


def test_physical_link_budget_respects_atmosphere_config() -> None:
    cfg_low = AtmosphereConfig(molecular_extinction_per_km=0.001)
    cfg_high = AtmosphereConfig(molecular_extinction_per_km=1.0)
    lb_low = _build(atmosphere_config=cfg_low)
    lb_high = _build(atmosphere_config=cfg_high)
    beam_low = next(s.efficiency for s in lb_low.stages if s.name == "beam")
    beam_high = next(s.efficiency for s in lb_high.stages if s.name == "beam")
    assert beam_high < beam_low


def test_canonical_constructor_unchanged_by_physical_extension() -> None:
    """The old constructor still works with the same signature."""
    lb = build_canonical_link_budget(
        input_power_w=100.0,
        transmitter_eff=0.5,
        beam_eff=0.7,
        receiver_eff=0.2,
        battery_eff=0.9,
    )
    assert lb.end_to_end_efficiency == pytest.approx(0.5 * 0.7 * 0.2 * 0.9, rel=1e-12)
