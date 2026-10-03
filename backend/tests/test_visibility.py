"""Unit tests for visibility windows and eclipse detection.

Roadmap tasks:
    s1-3 Visibility window calculator - physical plausibility and
        structural properties (contiguous, sorted, non-overlapping)
    s1-4 Eclipse period detection - physically plausible eclipse fraction
        and deterministic output
"""

from datetime import timedelta
from itertools import pairwise
from pathlib import Path

import numpy as np
import pytest
from skyfield.api import load  # type: ignore[import-untyped]

from app.physics.orbital import (
    AU_KM,
    R_EARTH_KM,
    GroundNode,
    Satellite,
    sun_position_eci_km,
    visibility_windows,
)

FIXTURE = Path(__file__).parent / "fixtures" / "iss.tle"
TS = load.timescale()


@pytest.fixture
def iss() -> Satellite:
    return Satellite.from_tle_file(FIXTURE)


@pytest.fixture
def greenbelt() -> GroundNode:
    # NASA Goddard Space Flight Center, Greenbelt, Maryland.
    return GroundNode("Greenbelt", 38.99, -76.84, 50.0)


# --- Constants --------------------------------------------------------------


def test_earth_radius_constant() -> None:
    assert 6_000.0 < R_EARTH_KM < 7_000.0


# --- Sun position -----------------------------------------------------------


def test_sun_distance_is_plausible(iss: Satellite) -> None:
    t = TS.from_datetime(iss.epoch_utc)
    r_sun = sun_position_eci_km(t)
    r_km = float(np.linalg.norm(r_sun))
    # Earth's orbit varies between ~0.983 and ~1.017 AU.
    assert 0.98 * AU_KM < r_km < 1.02 * AU_KM


# --- Eclipse detection (s1-4) -----------------------------------------------


def test_is_in_eclipse_returns_bool(iss: Satellite) -> None:
    t = TS.from_datetime(iss.epoch_utc)
    result = iss.is_in_eclipse(t)
    assert isinstance(result, bool)


def test_is_in_eclipse_is_deterministic(iss: Satellite) -> None:
    t = TS.from_datetime(iss.epoch_utc)
    assert iss.is_in_eclipse(t) == iss.is_in_eclipse(t)


def test_eclipse_fraction_plausible_over_one_day(iss: Satellite) -> None:
    """Over 24 hours, the ISS spends between 0% and 45% of the time in
    Earth's shadow. Zero is possible when the beta angle is high enough
    that the orbit never intersects the shadow cylinder."""
    t0 = iss.epoch_utc
    n_samples = 288  # one sample every 5 minutes for 24 hours
    eclipsed = 0
    for i in range(n_samples):
        t = TS.from_datetime(t0 + timedelta(minutes=5 * i))
        if iss.is_in_eclipse(t):
            eclipsed += 1
    fraction = eclipsed / n_samples
    assert 0.0 <= fraction <= 0.45, f"Eclipse fraction {fraction:.3f} out of range"


# --- Visibility windows (s1-3) ----------------------------------------------


def test_visibility_windows_returns_tuple(iss: Satellite, greenbelt: GroundNode) -> None:
    t_start = iss.epoch_utc
    t_end = t_start + timedelta(hours=6)
    windows = visibility_windows(iss, greenbelt, t_start, t_end, step_seconds=30.0)
    assert isinstance(windows, tuple)


def test_visibility_at_least_one_pass_in_24h(iss: Satellite, greenbelt: GroundNode) -> None:
    t_start = iss.epoch_utc
    t_end = t_start + timedelta(hours=24)
    windows = visibility_windows(iss, greenbelt, t_start, t_end, step_seconds=60.0)
    assert len(windows) >= 1, "Expected at least one ISS pass over Greenbelt in 24h"


def test_windows_are_sorted_and_non_overlapping(iss: Satellite, greenbelt: GroundNode) -> None:
    t_start = iss.epoch_utc
    t_end = t_start + timedelta(hours=24)
    windows = visibility_windows(iss, greenbelt, t_start, t_end, step_seconds=60.0)
    for a, b in pairwise(windows):
        assert a.start_utc <= a.end_utc
        assert a.end_utc <= b.start_utc, "Windows overlap or are out of order"


def test_each_window_peak_exceeds_min_elevation(iss: Satellite, greenbelt: GroundNode) -> None:
    t_start = iss.epoch_utc
    t_end = t_start + timedelta(hours=24)
    min_elev = 10.0
    windows = visibility_windows(
        iss,
        greenbelt,
        t_start,
        t_end,
        step_seconds=60.0,
        min_elevation_deg=min_elev,
    )
    for w in windows:
        assert w.peak_elevation_deg >= min_elev
        assert w.duration_seconds > 0.0


def test_visibility_rejects_zero_step(iss: Satellite, greenbelt: GroundNode) -> None:
    t_start = iss.epoch_utc
    t_end = t_start + timedelta(hours=1)
    with pytest.raises(ValueError):
        visibility_windows(iss, greenbelt, t_start, t_end, step_seconds=0.0)


def test_visibility_rejects_reversed_range(iss: Satellite, greenbelt: GroundNode) -> None:
    t_start = iss.epoch_utc
    with pytest.raises(ValueError):
        visibility_windows(iss, greenbelt, t_start, t_start, step_seconds=30.0)
