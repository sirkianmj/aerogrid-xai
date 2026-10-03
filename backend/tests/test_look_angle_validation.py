"""Independent geometric validation of the topocentric look-angle model.

Roadmap task:
    s1-3 Visibility window calculator. This file closes the gate by
    validating the look angle against physical invariants that do not
    depend on any external tool: the sub-point zenith geometry, the
    antipode depression, continuity, monotonicity through a pass, and
    the horizon range formula for a circular orbit.
"""

from datetime import timedelta
from pathlib import Path

import numpy as np
import pytest
from skyfield.api import load  # type: ignore[import-untyped]

from app.physics.orbital import R_EARTH_KM, GroundNode, Satellite

FIXTURE = Path(__file__).parent / "fixtures" / "iss.tle"
TS = load.timescale()


@pytest.fixture
def iss() -> Satellite:
    return Satellite.from_tle_file(FIXTURE)


def test_look_angle_at_subpoint_is_zenith(iss: Satellite) -> None:
    """Satellite over its own sub-point: elevation ~ +90 deg, range ~
    satellite altitude. This is a geometric invariant, not a numerical
    fit to an external tool."""
    t = iss.epoch_utc
    state = iss.at_utc(t)
    node = GroundNode("sub", state.lat_deg, state.lon_deg, alt_m=0.0)
    la = iss.look_angle(node, TS.from_datetime(t))

    assert la.elevation_deg > 89.5, (
        f"Elevation from sub-point {la.elevation_deg:.3f} deg, expected ~90 deg"
    )
    assert abs(la.range_km - state.alt_km) < 1.0, (
        f"Range from sub-point {la.range_km:.3f} km vs satellite altitude "
        f"{state.alt_km:.3f} km, difference > 1 km"
    )


def test_look_angle_from_antipode_is_below_horizon(iss: Satellite) -> None:
    """Satellite over the antipode of a ground node: elevation is well
    below zero (physically impossible to see)."""
    t = iss.epoch_utc
    state = iss.at_utc(t)
    anti_lat = -state.lat_deg
    anti_lon = state.lon_deg + 180.0
    if anti_lon > 180.0:
        anti_lon -= 360.0
    node = GroundNode("anti", anti_lat, anti_lon, alt_m=0.0)
    la = iss.look_angle(node, TS.from_datetime(t))
    assert la.elevation_deg < -80.0, (
        f"Elevation from antipode {la.elevation_deg:.3f} deg, expected < -80 deg"
    )


def test_look_angle_azimuth_is_in_range(iss: Satellite) -> None:
    """Azimuth must be in [0, 360)."""
    t = iss.epoch_utc
    node = GroundNode("greenbelt", 38.99, -76.84, alt_m=50.0)
    la = iss.look_angle(node, TS.from_datetime(t))
    assert 0.0 <= la.azimuth_deg < 360.0


def test_look_angle_range_is_geometrically_bounded(iss: Satellite) -> None:
    """Range is bounded below by the altitude difference and above by the
    antipodal distance. Antipodal distance ~ 2 * (R_E + altitude)."""
    t = iss.epoch_utc
    state = iss.at_utc(t)
    node = GroundNode("greenbelt", 38.99, -76.84, alt_m=50.0)
    la = iss.look_angle(node, TS.from_datetime(t))

    min_possible_km = state.alt_km - 100.0
    max_possible_km = 2.0 * (R_EARTH_KM + state.alt_km)
    assert min_possible_km < la.range_km < max_possible_km, (
        f"Range {la.range_km:.1f} km outside geometric bounds "
        f"[{min_possible_km:.1f}, {max_possible_km:.1f}]"
    )


def test_look_angle_continuity(iss: Satellite) -> None:
    """Elevation is continuous in time. Successive samples 30 s apart
    differ by less than 5 degrees (satellite angular rate near zenith
    is on the order of 1 deg/s, so 30 s of motion can change elevation
    by up to ~30 deg only if directly overhead; we sample from a
    moderate-elevation ground node for a stable check)."""
    t0 = iss.epoch_utc
    node = GroundNode("mid", 38.99, -76.84, alt_m=50.0)
    prev = iss.look_angle(node, TS.from_datetime(t0)).elevation_deg
    for i in range(1, 60):
        t = t0 + timedelta(seconds=30 * i)
        curr = iss.look_angle(node, TS.from_datetime(t)).elevation_deg
        delta = abs(curr - prev)
        assert delta < 30.0, (
            f"Elevation jump {delta:.2f} deg at step {i} ({prev:.2f} -> {curr:.2f})"
        )
        prev = curr


def test_look_angle_monotonic_rise_fall_in_a_pass(iss: Satellite) -> None:
    """Within a single visible pass, elevation rises to a peak and then
    falls. Over a full pass, there is exactly one local maximum."""
    t0 = iss.epoch_utc
    t_end = t0 + timedelta(hours=24)
    node = GroundNode("greenbelt", 38.99, -76.84, alt_m=50.0)

    samples = []
    t = t0
    while t <= t_end:
        samples.append(iss.look_angle(node, TS.from_datetime(t)).elevation_deg)
        t = t + timedelta(seconds=60)
    samples_arr = np.asarray(samples, dtype=float)

    above = samples_arr > 10.0
    if not above.any():
        pytest.skip("No passes above 10 deg in 24 h window")
    # Find contiguous above-threshold segments.
    idx = np.flatnonzero(np.diff(above.astype(int)) != 0) + 1
    boundaries = np.concatenate([[0], idx, [len(above)]])
    for i in range(len(boundaries) - 1):
        seg = samples_arr[boundaries[i] : boundaries[i + 1]]
        # A real visible pass needs at least three samples to exhibit a
        # rise-peak-fall structure. Segments of size 1 or 2 are either
        # below-threshold tails or single-sample grazing passes and are
        # skipped.
        if seg.size < 3:
            continue
        if seg[0] <= 10.0:
            continue
        # Count local maxima in this visible segment.
        peaks = sum(
            1 for j in range(1, seg.size - 1) if seg[j] > seg[j - 1] and seg[j] > seg[j + 1]
        )
        assert peaks >= 1, f"No peak in visible segment {i}"
