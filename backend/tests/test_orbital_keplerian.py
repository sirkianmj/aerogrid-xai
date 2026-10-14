"""Tests for Satellite.from_keplerian.

The contract: a user-supplied mean Keplerian element set produces a
Satellite whose SGP4 propagation at the element epoch agrees with the
analytic prediction from those elements (altitude for circular orbits,
period from Kepler's third law). These are physical-plausibility
assertions, not position-vector comparisons; the same discipline used
for TLE tests in test_orbital.py.
"""

from __future__ import annotations

import math
from datetime import UTC, datetime

import pytest

from app.physics.orbital import Satellite

_MU_WGS72_KM3_S2 = 398_600.8
_EARTH_MEAN_RADIUS_KM = 6371.0
_EPOCH = datetime(2026, 10, 14, 12, 0, 0, tzinfo=UTC)


def _period_from_kepler(a_km: float) -> float:
    return 2.0 * math.pi * math.sqrt(a_km**3 / _MU_WGS72_KM3_S2)


def test_circular_leo_altitude_at_epoch() -> None:
    a_km = _EARTH_MEAN_RADIUS_KM + 400.0
    sat = Satellite.from_keplerian(
        name="TEST-LEO",
        epoch_utc=_EPOCH,
        a_km=a_km,
        e=0.0,
        i_deg=51.6,
        raan_deg=0.0,
        argp_deg=0.0,
        m0_deg=0.0,
    )
    sv = sat.at_utc(_EPOCH)
    # Circular LEO at 400 km above mean radius. The WGS-84 subpoint
    # altitude will differ from the geocentric radius by up to ~20 km
    # because of the ellipsoid flattening; allow a generous window.
    assert 350.0 < sv.alt_km < 450.0
    assert sv.speed_km_s > 7.0
    assert sv.speed_km_s < 8.0


def test_circular_geo_altitude_at_epoch() -> None:
    a_km = 42_164.0
    sat = Satellite.from_keplerian(
        name="TEST-GEO",
        epoch_utc=_EPOCH,
        a_km=a_km,
        e=0.0,
        i_deg=0.05,
        raan_deg=0.0,
        argp_deg=0.0,
        m0_deg=0.0,
    )
    sv = sat.at_utc(_EPOCH)
    assert 35_000.0 < sv.alt_km < 36_500.0
    assert 2.5 < sv.speed_km_s < 3.5


def test_period_matches_kepler_third_law() -> None:
    a_km = 7_000.0
    sat = Satellite.from_keplerian(
        name="TEST",
        epoch_utc=_EPOCH,
        a_km=a_km,
        e=0.001,
        i_deg=30.0,
        raan_deg=10.0,
        argp_deg=20.0,
        m0_deg=40.0,
    )
    # SGP4 stores mean motion in rev/day; invert to period and compare
    # against 2 pi sqrt(a^3/mu). The two agree to first order; the small
    # difference is the SGP4 short-period correction.
    period_sgp4 = sat.period_seconds
    period_kepler = _period_from_kepler(a_km)
    assert period_sgp4 == pytest.approx(period_kepler, rel=0.01)


def test_rejects_eccentricity_one_or_more() -> None:
    for bad_e in (1.0, 1.5):
        with pytest.raises(ValueError, match="eccentricity"):
            Satellite.from_keplerian(
                name="TEST",
                epoch_utc=_EPOCH,
                a_km=7_000.0,
                e=bad_e,
                i_deg=0.0,
                raan_deg=0.0,
                argp_deg=0.0,
                m0_deg=0.0,
            )


def test_rejects_nonpositive_semimajor_axis() -> None:
    with pytest.raises(ValueError, match="a_km"):
        Satellite.from_keplerian(
            name="TEST",
            epoch_utc=_EPOCH,
            a_km=0.0,
            e=0.0,
            i_deg=0.0,
            raan_deg=0.0,
            argp_deg=0.0,
            m0_deg=0.0,
        )


def test_rejects_inclination_outside_0_to_180() -> None:
    with pytest.raises(ValueError, match="inclination"):
        Satellite.from_keplerian(
            name="TEST",
            epoch_utc=_EPOCH,
            a_km=7_000.0,
            e=0.0,
            i_deg=200.0,
            raan_deg=0.0,
            argp_deg=0.0,
            m0_deg=0.0,
        )


def test_is_deterministic() -> None:
    s1 = Satellite.from_keplerian(
        name="TEST",
        epoch_utc=_EPOCH,
        a_km=7_100.0,
        e=0.01,
        i_deg=45.0,
        raan_deg=15.0,
        argp_deg=25.0,
        m0_deg=35.0,
    )
    s2 = Satellite.from_keplerian(
        name="TEST",
        epoch_utc=_EPOCH,
        a_km=7_100.0,
        e=0.01,
        i_deg=45.0,
        raan_deg=15.0,
        argp_deg=25.0,
        m0_deg=35.0,
    )
    sv1 = s1.at_utc(_EPOCH)
    sv2 = s2.at_utc(_EPOCH)
    assert sv1.lat_deg == sv2.lat_deg
    assert sv1.lon_deg == sv2.lon_deg
    assert sv1.alt_km == sv2.alt_km
