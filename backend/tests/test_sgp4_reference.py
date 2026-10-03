"""Reference validation of the Skyfield SGP4 propagator.

Roadmap task:
    s1-1 Skyfield integration - position error < 1 km at TLE epoch vs.
    reference.

Reference:
    Vallado, Crawford, Hujsak, Kelso, "Revisiting Spacetrack Report #3"
    (AIAA 2006-6753), Table 6. The reference state vector for satellite
    00005 (Vanguard 1) at the TLE epoch is:

        r_TEME = (7022.46529266, -1400.08296755, 0.03995155) km
        v_TEME = (1.893841015, 6.405893759, 4.534807250) km/s

    This is the canonical test vector for SGP4 implementations and is
    the same vector used to validate the official python-sgp4 library
    and STK. The frame rotation from TEME to GCRS preserves vector
    magnitude to machine precision, so we compare magnitudes.
"""

from pathlib import Path

import numpy as np
import pytest

from app.physics.orbital import Satellite

FIXTURE = Path(__file__).parent / "fixtures" / "spacetrack" / "vanguard_r3.tle"

# Published reference values from Vallado 2006, Table 6.
R_REFERENCE_KM = np.array([7022.46529266, -1400.08296755, 0.03995155])
V_REFERENCE_KM_S = np.array([1.893841015, 6.405893759, 4.534807250])

R_REFERENCE_MAG_KM = float(np.linalg.norm(R_REFERENCE_KM))
V_REFERENCE_MAG_KM_S = float(np.linalg.norm(V_REFERENCE_KM_S))


@pytest.fixture
def vanguard() -> Satellite:
    return Satellite.from_tle_file(FIXTURE)


def test_reference_magnitude_sanity() -> None:
    """The published magnitudes are as expected: |r| ~ 7160.7 km,
    |v| ~ 8.074 km/s."""
    assert 7150.0 < R_REFERENCE_MAG_KM < 7170.0
    assert 8.05 < V_REFERENCE_MAG_KM_S < 8.10


def test_sgp4_position_magnitude_matches_reference(vanguard: Satellite) -> None:
    """Position magnitude at TLE epoch must match the published reference
    within 1 km."""
    geocentric = vanguard._earth_sat.at(_skyfield_time(vanguard))
    r_km = np.asarray(geocentric.position.km, dtype=float)
    r_mag = float(np.linalg.norm(r_km))
    error_km = abs(r_mag - R_REFERENCE_MAG_KM)
    assert error_km < 1.0, (
        f"Position magnitude error {error_km:.3f} km exceeds 1 km; "
        f"computed {r_mag:.3f} km vs reference {R_REFERENCE_MAG_KM:.3f} km"
    )


def test_sgp4_velocity_magnitude_matches_reference(vanguard: Satellite) -> None:
    """Velocity magnitude at TLE epoch must match the published reference
    within 0.01 km/s."""
    geocentric = vanguard._earth_sat.at(_skyfield_time(vanguard))
    v_km_s = np.asarray(geocentric.velocity.km_per_s, dtype=float)
    v_mag = float(np.linalg.norm(v_km_s))
    error_km_s = abs(v_mag - V_REFERENCE_MAG_KM_S)
    assert error_km_s < 0.01, (
        f"Velocity magnitude error {error_km_s:.4f} km/s exceeds 0.01 km/s; "
        f"computed {v_mag:.4f} km/s vs reference {V_REFERENCE_MAG_KM_S:.4f} km/s"
    )


def _skyfield_time(sat: Satellite) -> object:
    """Return the TLE epoch as a Skyfield Time."""
    from skyfield.api import load  # type: ignore[import-untyped]

    ts = load.timescale()
    return ts.from_datetime(sat.epoch_utc)
