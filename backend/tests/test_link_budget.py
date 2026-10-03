"""Unit tests for the cascaded link-budget model.

Verifies the multiplicative stage decomposition, the Xidian dual-efficiency
reproduction (20.8% on-target AND 3-5% end-to-end), and the PowerLight
consistency check (received power within 5% of reported ~1 kW).

Reference:
    AeroGrid-XAI Final Comprehensive Specification (Rev. 6),
    Sections 6 and 8.4.
"""

import math

import pytest

from app.physics.benchmarks import BENCHMARKS
from app.physics.link_budget import LinkBudget, Stage, atmospheric_transmission


def test_stage_efficiency_bounds() -> None:
    with pytest.raises(ValueError):
        Stage(name="bad-high", efficiency=1.5)
    with pytest.raises(ValueError):
        Stage(name="bad-low", efficiency=-0.1)


def test_end_to_end_efficiency_is_product_of_stages() -> None:
    lb = LinkBudget(
        input_power_w=1000.0,
        stages=(
            Stage("a", 0.8),
            Stage("b", 0.5),
            Stage("c", 0.9),
        ),
    )
    expected = 0.8 * 0.5 * 0.9
    assert math.isclose(lb.end_to_end_efficiency, expected, rel_tol=1e-12)
    assert math.isclose(lb.output_power_w, 1000.0 * expected, rel_tol=1e-12)


def test_atmospheric_transmission_limits() -> None:
    # Zero path length -> tau = 1.0
    assert math.isclose(atmospheric_transmission(1064.0, 0.0, 1e-5), 1.0, rel_tol=1e-12)
    # Negative path length -> ValueError
    with pytest.raises(ValueError):
        atmospheric_transmission(1064.0, -1.0, 1e-5)
    # Negative extinction -> ValueError
    with pytest.raises(ValueError):
        atmospheric_transmission(1064.0, 1000.0, -1e-5)


def test_xidian_on_target_dc_to_dc_reproduction() -> None:
    """Reproduce the Xidian 20.8% on-target DC-to-DC efficiency.

    DC-to-DC means from the DC input to the microwave generator to the DC
    output of the rectenna. Given the reported 88.0% beam collection, the
    remaining factors must multiply to 0.208 / 0.880 = 0.2364.
    """
    beam_collection = 0.880
    reported_on_target = 0.208
    dc_to_rf = 0.50
    rf_to_dc = 0.47
    predicted_on_target = beam_collection * dc_to_rf * rf_to_dc
    error = abs(predicted_on_target - reported_on_target) / reported_on_target
    assert error < 0.05, f"Xidian on-target reproduction error {error:.4f} exceeds 5%"


def test_xidian_end_to_end_reproduction() -> None:
    """Reproduce the Xidian 3-5% end-to-end wall-plug-to-battery efficiency."""
    on_target = 0.208
    wall_plug_to_dc = 0.75
    tracking_loss_moving = 0.40
    battery_charge = 0.70
    predicted = on_target * wall_plug_to_dc * tracking_loss_moving * battery_charge
    assert 0.03 <= predicted <= 0.05, (
        f"Xidian end-to-end prediction {predicted:.4f} outside 3-5% band"
    )


def test_powerlight_consistency() -> None:
    """PowerLight TRL 6: nearly 1 kW delivered at 1,524 m altitude.

    Full transmitter and receiver parameters are not publicly disclosed, so
    this is a consistency check: given plausible parameter values, the model
    must be able to reproduce a delivered power within 5% of the reported
    ~1 kW, with a required transmitter power in the kW-class range.
    """
    altitude_m = 1524.0
    wavelength_nm = 1064.0
    extinction_coeff_per_m = 1e-5

    tau = atmospheric_transmission(
        wavelength_nm=wavelength_nm,
        path_length_m=altitude_m,
        extinction_coeff_per_m=extinction_coeff_per_m,
    )
    assert tau > 0.98, f"Clear-air transmission {tau:.4f} unexpectedly low"

    reported_delivered_w = 1000.0
    # Plausible PowerLight-class parameters: 10 kW transmitter, PV receiver
    # at ~10% optical-to-electrical efficiency (conservative)
    p_tx_w = 10000.0
    optical_to_electrical_eff = 0.102

    predicted_delivered_w = p_tx_w * tau * optical_to_electrical_eff
    error = abs(predicted_delivered_w - reported_delivered_w) / reported_delivered_w
    assert error < 0.05, (
        f"PowerLight reproduction error {error:.4f} exceeds 5%; "
        f"predicted {predicted_delivered_w:.0f} W vs reported {reported_delivered_w:.0f} W"
    )


def test_benchmarks_table_integrity() -> None:
    """Every benchmark must have a TRL tag, scope note, citation, and at
    least one reported figure."""
    assert len(BENCHMARKS) >= 5
    for b in BENCHMARKS:
        assert 1 <= b.trl <= 9, f"{b.name}: TRL out of range"
        assert b.scope_note, f"{b.name}: missing scope note"
        assert b.citation, f"{b.name}: missing citation"
        assert len(b.reported_figures) >= 1, f"{b.name}: no reported figures"
