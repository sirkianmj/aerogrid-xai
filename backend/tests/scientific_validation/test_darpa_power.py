"""DARPA POWER program / NRL - TRL 5 (Section 6).

Fixed ground-to-ground optical power beaming at White Sands Missile
Range: >800 W delivered over 8.6 km (5.3 mi) in a 30-second
transmission.

Validates that the transmission coefficient over 8.6 km at 1,064 nm
with clear-air extinction is physically plausible; does NOT claim
moving-platform validation (the demonstration was fixed-to-fixed).

Epistemic categories: the 800 W and 8.6 km figures are [PHYSICAL
MEASUREMENT]. The transmission coefficient is an [ESTIMATED MODEL]
output over clear-air conditions.
"""

from __future__ import annotations

import math

from app.physics.benchmarks import BENCHMARKS
from app.physics.link_budget import atmospheric_transmission


def _darpa_figures() -> dict[str, float]:
    d = next(b for b in BENCHMARKS if "DARPA" in b.name)
    return {label: value for label, value, _units in d.reported_figures}


def test_table_carries_800w_over_8600m() -> None:
    figures = _darpa_figures()
    power = next(v for k, v in figures.items() if "power" in k.lower())
    distance = next(v for k, v in figures.items() if "distance" in k.lower())
    assert math.isclose(power, 800.0, rel_tol=1e-12), power
    assert math.isclose(distance, 8600.0, rel_tol=1e-12), distance


def test_transmission_plausible_over_8_6km() -> None:
    """Clear-air 1,064 nm propagation over 8.6 km with extinction
    1e-5 /m: tau = exp(-0.086) ~= 0.918. The assertion bound is
    conservative: tau in (0.85, 1.0) permits a range of realistic
    extinction coefficients while still rejecting a numerically
    implausible model."""
    tau = atmospheric_transmission(
        wavelength_nm=1064.0,
        path_length_m=8600.0,
        extinction_coeff_per_m=1e-5,
    )
    assert 0.85 < tau < 1.0, f"Darpa-range tau = {tau:.4f}; expected in (0.85, 1.0)"


def test_scope_note_rejects_moving_platform_claim() -> None:
    """The DARPA POWER demonstration does NOT validate moving-platform
    dynamics. The scope note must say 'fixed'."""
    d = next(b for b in BENCHMARKS if "DARPA" in b.name)
    note = d.scope_note.lower()
    assert "fixed" in note, d.scope_note
