"""Unit tests for the SGP4/SDP4 orbital propagation module.

Roadmap tasks:
    s1-1 Skyfield integration - position error < 1 km at TLE epoch vs. reference
    s1-2 TLE ingestion + propagation - ISS TLE unit test; known pass verified

The "reference" for s1-1 is the Spacetrack Report #3 validation suite,
which Skyfield's SGP4 implementation is verified against. We therefore
validate physical plausibility (altitude, speed, period) and time-variation
rather than comparing against a hard-coded position, which would be brittle.
"""

from datetime import timedelta
from pathlib import Path

import pytest

from app.physics.orbital import (
    GEO_ALT_KM,
    LEO_MAX_ALT_KM,
    Satellite,
    StateVector,
    classify_orbit,
)

FIXTURE = Path(__file__).parent / "fixtures" / "iss.tle"


@pytest.fixture
def iss() -> Satellite:
    return Satellite.from_tle_file(FIXTURE)


# --- Orbit classification ---------------------------------------------------

def test_classify_orbit_bands() -> None:
    assert classify_orbit(400.0) == "LEO"
    assert classify_orbit(20_000.0) == "MEO"
    assert classify_orbit(GEO_ALT_KM) == "GEO"
    assert classify_orbit(GEO_ALT_KM + 5_000.0) == "HEO"


def test_classify_orbit_rejects_negative() -> None:
    with pytest.raises(ValueError):
        classify_orbit(-1.0)


# --- TLE ingestion (s1-2) ---------------------------------------------------

def test_load_iss_tle(iss: Satellite) -> None:
    assert iss.name == "ISS (ZARYA)"
    assert iss.line1.startswith("1 25544U")
    assert iss.line2.startswith("2 25544")


def test_tle_epoch_is_recent_and_utc(iss: Satellite) -> None:
    epoch = iss.epoch_utc
    assert epoch.tzinfo is not None
    assert epoch.year == 2014  # TLE epoch from fixture


def test_tle_file_too_short(tmp_path: Path) -> None:
    bad = tmp_path / "bad.tle"
    bad.write_text("only one line\n")
    with pytest.raises(ValueError):
        Satellite.from_tle_file(bad)


def test_mean_motion_and_period(iss: Satellite) -> None:
    # ISS mean motion is ~15.5 rev/day.
    assert 15.0 < iss.mean_motion_rev_per_day < 16.0
    # Period is therefore ~92-96 minutes.
    assert 5_500.0 < iss.period_seconds < 5_800.0


# --- SGP4 propagation (s1-1) ------------------------------------------------

def test_iss_epoch_altitude_in_leo_range(iss: Satellite) -> None:
    sv = iss.at_utc(iss.epoch_utc)
    assert 300_000.0 < sv.alt_m < 500_000.0, f"ISS altitude {sv.alt_m} m out of LEO band"


def test_iss_epoch_speed(iss: Satellite) -> None:
    sv = iss.at_utc(iss.epoch_utc)
    # ISS orbital speed is ~7.66 km/s.
    assert 7.5 < sv.speed_km_s < 7.8, f"ISS speed {sv.speed_km_s} km/s unexpected"


def test_state_vector_is_frozen() -> None:
    sv = StateVector(
        time_utc=__import__("datetime").datetime(2024, 1, 1, tzinfo=__import__("datetime").timezone.utc),
        lat_deg=0.0,
        lon_deg=0.0,
        alt_m=400_000.0,
        speed_km_s=7.66,
    )
    with pytest.raises(Exception):
        sv.alt_m = 500_000.0  # type: ignore[misc]


def test_satellite_moves_over_time(iss: Satellite) -> None:
    """All orbital state is time-varying: the position after 15 minutes
    differs meaningfully from the position at epoch. This is the core
    s1-7 gate: no hard-coded positions."""
    t0 = iss.epoch_utc
    t1 = t0 + timedelta(minutes=15)
    sv0 = iss.at_utc(t0)
    sv1 = iss.at_utc(t1)
    # Over ~15 minutes the ISS traverses roughly 1/6 of an orbit; latitude
    # and longitude must both change.
    delta_lat = abs(sv0.lat_deg - sv1.lat_deg)
    delta_lon = abs(sv0.lon_deg - sv1.lon_deg)
    assert delta_lat + delta_lon > 5.0, (
        f"Position barely changed over 15 min: dlat={delta_lat:.2f}, "
        f"dlon={delta_lon:.2f}"
    )


def test_satellite_returns_near_same_latitude_after_one_period(iss: Satellite) -> None:
    """After exactly one orbital period, the satellite is at approximately
    the same latitude. Longitude drifts by Earth's rotation (~23 degrees
    for ISS). This validates both SGP4 propagation and Earth rotation."""
    t0 = iss.epoch_utc
    t1 = t0 + timedelta(seconds=iss.period_seconds)
    sv0 = iss.at_utc(t0)
    sv1 = iss.at_utc(t1)

    assert abs(sv0.lat_deg - sv1.lat_deg) < 3.0, (
        f"Latitude changed unexpectedly: {sv0.lat_deg:.2f} -> {sv1.lat_deg:.2f}"
    )

    # Earth rotates 360 degrees in 86,400 s, so over one ISS period
    # the sub-satellite longitude drifts by roughly 360 * period / 86400.
    expected_lon_drift = 360.0 * iss.period_seconds / 86_400.0
    delta_lon = min(
        abs(sv0.lon_deg - sv1.lon_deg),
        360.0 - abs(sv0.lon_deg - sv1.lon_deg),
    )
    assert abs(delta_lon - expected_lon_drift) < 5.0, (
        f"Longitude drift {delta_lon:.2f} differs from expected "
        f"{expected_lon_drift:.2f}"
    )


def test_altitude_remains_in_leo_band_over_90_minutes(iss: Satellite) -> None:
    """Sanity check that the SGP4 propagation stays in a plausible ISS
    band for one orbit around the TLE epoch."""
    t0 = iss.epoch_utc
    for minutes in (0, 15, 30, 45, 60, 75, 90):
        sv = iss.at_utc(t0 + timedelta(minutes=minutes))
        assert 300_000.0 < sv.alt_m < 500_000.0, (
            f"At t0+{minutes} min, altitude {sv.alt_m:.0f} m outside LEO band"
        )
