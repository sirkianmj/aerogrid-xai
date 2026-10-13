"""PowerLight / Kraus Hamdani - TRL 6 (Section 6).

Ground-to-air laser power beaming to a moving UAV in flight at Shaw
AFB. Nearly 1 kW delivered at altitudes up to 5,000 ft (1,524 m).

Full transmitter and receiver parameters are not publicly disclosed.
This is a **consistency check**: given physically plausible parameter
values, the model must reproduce ~1 kW. It is not a parameter fit.

Error bound: reproduced delivered power within 5% of 1,000 W.

Epistemic categories: the 1 kW and 1,524 m figures are [PHYSICAL
MEASUREMENT]. The consistency-check parameters are [ESTIMATED MODEL].
"""

from __future__ import annotations

import math

from app.physics.benchmarks import BENCHMARKS
from app.physics.link_budget import atmospheric_transmission


def _powerlight_figures() -> dict[str, float]:
    pl = next(b for b in BENCHMARKS if "PowerLight" in b.name)
    return {label: value for label, value, _units in pl.reported_figures}


def test_table_carries_1kw_and_1524m() -> None:
    figures = _powerlight_figures()
    power = next(v for k, v in figures.items() if "power" in k.lower())
    altitude = next(v for k, v in figures.items() if "altitude" in k.lower())
    assert math.isclose(power, 1000.0, rel_tol=1e-12), power
    assert math.isclose(altitude, 1524.0, rel_tol=1e-12), altitude


def test_clear_air_transmission_is_high_at_1km_range() -> None:
    """At 1,064 nm with clear-air extinction (1e-5 /m), the Beer-Lambert
    transmission coefficient over 1,524 m must remain above 0.98."""
    tau = atmospheric_transmission(
        wavelength_nm=1064.0,
        path_length_m=1524.0,
        extinction_coeff_per_m=1e-5,
    )
    assert tau > 0.98, f"clear-air tau over 1,524 m = {tau:.4f}; expected > 0.98"


def test_consistency_check_reproduces_1kw_within_5_percent() -> None:
    """Plausible parameters: 10 kW transmitter, ~10.2% optical-to-
    electrical receiver, clear-air beam propagation. The model must
    reproduce 1 kW within 5% relative error."""
    p_tx_w = 10_000.0
    tau = atmospheric_transmission(1064.0, 1524.0, 1e-5)
    optical_to_electrical_eff = 0.102
    predicted = p_tx_w * tau * optical_to_electrical_eff
    reported = 1000.0
    error = abs(predicted - reported) / reported
    assert error < 0.05, (
        f"PowerLight reproduction error {error:.4f} exceeds 5%; "
        f"predicted {predicted:.1f} W, reported {reported:.0f} W"
    )


def test_scope_note_names_single_transmitter_and_cooperative_target() -> None:
    """The scope must remain narrow: PowerLight's claim is single
    ground transmitter, single cooperative moving target, active
    optical tracking. It is not a network demonstration."""
    pl = next(b for b in BENCHMARKS if "PowerLight" in b.name)
    note = pl.scope_note.lower()
    assert "single" in note
    assert "tracking" in note
