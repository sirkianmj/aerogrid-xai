"""Tests for physics/geometry.py and the rectenna zero-density fix."""

from __future__ import annotations

import math
import random

import pytest

from app.physics.geometry import (
    EARTH_RADIUS_M,
    H_ATMOSPHERE_M,
    geodetic_to_cartesian_m,
    has_line_of_sight,
    node_position_from_params_m,
    range_m,
    sample_direction_in_visible_cap,
    visible_cap_half_angle_rad,
)
from app.physics.geometry import atmospheric_path_length_m as _aplm
from app.physics.rectenna import rectenna_efficiency

# -- geodetic_to_cartesian_m ------------------------------------------------


def test_geodetic_to_cartesian_at_origin_meridian() -> None:
    x, y, z = geodetic_to_cartesian_m(0.0, 0.0, 0.0)
    assert x == pytest.approx(EARTH_RADIUS_M, rel=1e-12)
    assert y == pytest.approx(0.0, abs=1e-6)
    assert z == pytest.approx(0.0, abs=1e-6)


def test_geodetic_to_cartesian_at_north_pole() -> None:
    x, y, z = geodetic_to_cartesian_m(90.0, 0.0, 0.0)
    assert x == pytest.approx(0.0, abs=1e-6)
    assert y == pytest.approx(0.0, abs=1e-6)
    assert z == pytest.approx(EARTH_RADIUS_M, rel=1e-12)


def test_geodetic_to_cartesian_with_altitude() -> None:
    x, _, _ = geodetic_to_cartesian_m(0.0, 0.0, 500_000.0)
    assert x == pytest.approx(EARTH_RADIUS_M + 500_000.0, rel=1e-12)


# -- node_position_from_params_m --------------------------------------------


def test_node_position_uses_altitude_km_when_present() -> None:
    p = {"lat_deg": 0.0, "lon_deg": 0.0, "altitude_km": 500.0}
    x, _, _ = node_position_from_params_m(p)
    assert x == pytest.approx(EARTH_RADIUS_M + 500_000.0, rel=1e-12)


def test_node_position_uses_altitude_m_when_present() -> None:
    p = {"lat_deg": 0.0, "lon_deg": 0.0, "altitude_m": 100.0}
    x, _, _ = node_position_from_params_m(p)
    assert x == pytest.approx(EARTH_RADIUS_M + 100.0, rel=1e-12)


def test_node_position_defaults_altitude_to_zero() -> None:
    p = {"lat_deg": 0.0, "lon_deg": 0.0}
    x, _, _ = node_position_from_params_m(p)
    assert x == pytest.approx(EARTH_RADIUS_M, rel=1e-12)


# -- range_m -----------------------------------------------------------------


def test_range_between_antipodal_ground_points() -> None:
    a = geodetic_to_cartesian_m(0.0, 0.0, 0.0)
    b = geodetic_to_cartesian_m(0.0, 180.0, 0.0)
    assert range_m(a, b) == pytest.approx(2.0 * EARTH_RADIUS_M, rel=1e-9)


def test_range_between_satellite_and_subpoint() -> None:
    a = geodetic_to_cartesian_m(0.0, 0.0, 500_000.0)
    b = geodetic_to_cartesian_m(0.0, 0.0, 0.0)
    assert range_m(a, b) == pytest.approx(500_000.0, rel=1e-9)


# -- has_line_of_sight -------------------------------------------------------


def test_los_antipodal_ground_points_false() -> None:
    a = geodetic_to_cartesian_m(0.0, 0.0, 0.0)
    b = geodetic_to_cartesian_m(0.0, 180.0, 0.0)
    assert not has_line_of_sight(a, b)


def test_los_satellite_to_far_side_false() -> None:
    a = geodetic_to_cartesian_m(0.0, 0.0, 500_000.0)
    b = geodetic_to_cartesian_m(0.0, 180.0, 0.0)
    assert not has_line_of_sight(a, b)


def test_los_satellite_to_near_side_true() -> None:
    a = geodetic_to_cartesian_m(0.0, 0.0, 500_000.0)
    b = geodetic_to_cartesian_m(0.0, 5.0, 100.0)
    assert has_line_of_sight(a, b)


# -- atmospheric_path_length_m ----------------------------------------------


def test_atmospheric_path_ground_to_ground_is_full_range() -> None:
    a = geodetic_to_cartesian_m(0.0, 0.0, 0.0)
    b = geodetic_to_cartesian_m(0.1, 0.0, 0.0)
    assert _aplm(a, b) == pytest.approx(range_m(a, b), rel=1e-9)


def test_atmospheric_path_satellite_to_ground_is_shell() -> None:
    a = geodetic_to_cartesian_m(0.0, 0.0, 500_000.0)
    b = geodetic_to_cartesian_m(0.0, 0.0, 0.0)
    atm = _aplm(a, b)
    assert atm == pytest.approx(H_ATMOSPHERE_M, rel=1e-3)


def test_atmospheric_path_vacuum_to_vacuum_is_zero() -> None:
    a = geodetic_to_cartesian_m(0.0, 0.0, 500_000.0)
    b = geodetic_to_cartesian_m(0.5, 0.0, 500_000.0)
    assert _aplm(a, b) == 0.0


# -- visible_cap_half_angle_rad ---------------------------------------------


def test_visible_cap_gs_to_gs_is_zero() -> None:
    theta = visible_cap_half_angle_rad(EARTH_RADIUS_M, EARTH_RADIUS_M)
    assert theta == pytest.approx(0.0, abs=1e-9)


def test_visible_cap_leo_to_ground_matches_expected() -> None:
    """LEO at 500 km sees a ground station through ~22 deg half-angle."""
    theta_rad = visible_cap_half_angle_rad(EARTH_RADIUS_M + 500_000.0, EARTH_RADIUS_M)
    assert math.degrees(theta_rad) == pytest.approx(22.0, abs=1.0)


def test_visible_cap_geo_to_ground_matches_expected() -> None:
    """GEO sees ~81 deg."""
    theta_rad = visible_cap_half_angle_rad(EARTH_RADIUS_M + 35_786_000.0, EARTH_RADIUS_M)
    assert math.degrees(theta_rad) == pytest.approx(81.3, abs=1.0)


def test_visible_cap_rejects_below_surface_radius() -> None:
    with pytest.raises(ValueError, match="earth_radius_m"):
        visible_cap_half_angle_rad(EARTH_RADIUS_M - 1.0, EARTH_RADIUS_M)


# -- sample_direction_in_visible_cap ----------------------------------------


def test_sample_direction_within_cap() -> None:
    """Every sampled direction is within the cap half-angle of centre."""
    rng = random.Random(12345)
    for _ in range(500):
        lat, lon = sample_direction_in_visible_cap(0.0, 0.0, 0.3, rng)
        # Angular separation from (0, 0) is just |lat| when lon-free
        # at lat=0; convert to direction and take dot product with (1,0,0)
        lr = math.radians(lat)
        lr_lon = math.radians(lon)
        dx = math.cos(lr) * math.cos(lr_lon)
        # dot product with source direction (1, 0, 0)
        cos_theta = dx
        theta = math.acos(max(-1.0, min(1.0, cos_theta)))
        assert theta <= 0.3 + 1e-9, f"sampled theta {theta} > 0.3"


def test_sample_direction_full_sphere_covers_all_latitudes() -> None:
    """A cap of pi covers the whole sphere."""
    rng = random.Random(99)
    lats = [sample_direction_in_visible_cap(0.0, 0.0, math.pi, rng)[0] for _ in range(2000)]
    assert min(lats) < -80.0
    assert max(lats) > 80.0


def test_sample_direction_zero_cap_returns_centre() -> None:
    rng = random.Random(1)
    lat, lon = sample_direction_in_visible_cap(45.0, 60.0, 0.0, rng)
    assert lat == pytest.approx(45.0, abs=1e-9)
    assert lon == pytest.approx(60.0, abs=1e-9)


def test_sample_direction_rejects_bad_half_angle() -> None:
    with pytest.raises(ValueError, match="half_angle_rad"):
        sample_direction_in_visible_cap(0.0, 0.0, -0.1, random.Random(0))
    with pytest.raises(ValueError, match="half_angle_rad"):
        sample_direction_in_visible_cap(0.0, 0.0, math.pi + 0.1, random.Random(0))


# -- rectenna zero-density fix ----------------------------------------------


def test_rectenna_zero_density_returns_zero() -> None:
    assert rectenna_efficiency(0.0, 5.8) == 0.0


def test_rectenna_negative_density_raises() -> None:
    with pytest.raises(ValueError, match="must be >= 0"):
        rectenna_efficiency(-1.0, 5.8)


def test_rectenna_non_finite_density_raises() -> None:
    with pytest.raises(ValueError, match="must be finite"):
        rectenna_efficiency(float("nan"), 5.8)
    with pytest.raises(ValueError, match="must be finite"):
        rectenna_efficiency(float("inf"), 5.8)


def test_rectenna_tiny_density_returns_tiny_efficiency() -> None:
    """Positive tiny density still evaluates; only exactly 0 short-circuits."""
    eta = rectenna_efficiency(1e-12, 5.8)
    assert eta > 0.0
    assert eta < 1e-100
