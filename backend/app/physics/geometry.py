"""Spherical-Earth geometry for link, LOS, and atmospheric path length.

Positions are 3D Cartesian in metres, with the origin at the Earth's
centre, the z-axis through the north pole, and the x-axis through the
(0, 0) meridian. The Earth is modelled as a sphere of radius
``EARTH_RADIUS_M``; WGS-84 differs by up to ~21 km at any point, a
documented simplification (docs/ENCODER_PHYSICS_INTEGRATION.md,
Decision 1).

This module is pure math. It imports nothing from ``app.discovery`` or
``app.verification``, so it can be used by physics modules, discovery
modules, and verification modules without creating an import cycle.
"""

from __future__ import annotations

import math
import random
from collections.abc import Mapping

EARTH_RADIUS_M = 6_371_000.0
"""[ESTIMATED] Spherical-Earth radius. WGS-84 differs by up to ~21 km
at any given point; a spherical model is a documented simplification
(docs/ENCODER_PHYSICS_INTEGRATION.md, Decision 1)."""

SPEED_OF_LIGHT_M_PER_S = 299_792_458.0
"""[SOURCED] Exact speed of light in vacuum, m/s (SI definition)."""

H_ATMOSPHERE_M = 20_000.0
"""[ESTIMATED] Thickness of the atmosphere shell used for atmospheric
path-length clipping. The atmosphere has no sharp boundary; 20 km is a
first-order choice covering the troposphere plus low stratosphere. A
density-resolved profile is deferred (docs/ENCODER_PHYSICS_INTEGRATION.md,
Decision 7)."""


def geodetic_to_cartesian_m(
    lat_deg: float,
    lon_deg: float,
    alt_m: float,
    *,
    earth_radius_m: float = EARTH_RADIUS_M,
) -> tuple[float, float, float]:
    """Convert a geodetic position to 3D Cartesian coordinates.

    Args:
        lat_deg: Latitude in degrees.
        lon_deg: Longitude in degrees.
        alt_m: Altitude above the spherical Earth surface, in metres.
        earth_radius_m: Earth radius used for the conversion.

    Returns:
        (x, y, z) in metres.
    """
    r = earth_radius_m + alt_m
    lat_rad = math.radians(lat_deg)
    lon_rad = math.radians(lon_deg)
    return (
        r * math.cos(lat_rad) * math.cos(lon_rad),
        r * math.cos(lat_rad) * math.sin(lon_rad),
        r * math.sin(lat_rad),
    )


def node_position_from_params_m(
    params: Mapping[str, float],
    *,
    earth_radius_m: float = EARTH_RADIUS_M,
) -> tuple[float, float, float]:
    """Return the 3D Cartesian position of a node from its parameter map.

    Latitude and longitude are read from ``lat_deg`` and ``lon_deg``.
    Altitude is read from ``altitude_km`` if present (satellite kinds),
    otherwise from ``altitude_m`` (UAVs and ground stations), otherwise
    defaults to 0 m.

    Args:
        params: A mapping of node parameters.
        earth_radius_m: Earth radius used for the conversion.

    Returns:
        (x, y, z) in metres.
    """
    lat_deg = float(params["lat_deg"])
    lon_deg = float(params["lon_deg"])
    if "altitude_km" in params:
        alt_m = float(params["altitude_km"]) * 1000.0
    elif "altitude_m" in params:
        alt_m = float(params["altitude_m"])
    else:
        alt_m = 0.0
    return geodetic_to_cartesian_m(lat_deg, lon_deg, alt_m, earth_radius_m=earth_radius_m)


def range_m(
    p_a: tuple[float, float, float],
    p_b: tuple[float, float, float],
) -> float:
    """Euclidean distance between two 3D positions, in metres."""
    dx = p_b[0] - p_a[0]
    dy = p_b[1] - p_a[1]
    dz = p_b[2] - p_a[2]
    return float(math.sqrt(dx * dx + dy * dy + dz * dz))


def has_line_of_sight(
    p_a: tuple[float, float, float],
    p_b: tuple[float, float, float],
    *,
    earth_radius_m: float = EARTH_RADIUS_M,
    grazing_tolerance: float = 1e-6,
) -> bool:
    """True if the straight segment between two points clears the Earth.

    Computes the minimum distance from the Earth's centre to the closed
    segment [A, B] and compares to the Earth radius. A small grazing
    tolerance (``grazing_tolerance * earth_radius_m``) allows tangent
    segments to count as line of sight.
    """
    abx = p_b[0] - p_a[0]
    aby = p_b[1] - p_a[1]
    abz = p_b[2] - p_a[2]
    ab_dot_ab = abx * abx + aby * aby + abz * abz
    if ab_dot_ab <= 0.0:
        d_min = math.sqrt(p_a[0] ** 2 + p_a[1] ** 2 + p_a[2] ** 2)
    else:
        t_star = -(p_a[0] * abx + p_a[1] * aby + p_a[2] * abz) / ab_dot_ab
        t_clamped = max(0.0, min(1.0, t_star))
        cx = p_a[0] + t_clamped * abx
        cy = p_a[1] + t_clamped * aby
        cz = p_a[2] + t_clamped * abz
        d_min = math.sqrt(cx * cx + cy * cy + cz * cz)
    return d_min >= earth_radius_m * (1.0 - grazing_tolerance)


def atmospheric_path_length_m(
    p_a: tuple[float, float, float],
    p_b: tuple[float, float, float],
    *,
    earth_radius_m: float = EARTH_RADIUS_M,
    h_atmosphere_m: float = H_ATMOSPHERE_M,
) -> float:
    """Length of the segment [A, B] inside the atmosphere shell.

    The atmosphere is modelled as a spherical shell between radii
    ``earth_radius_m`` and ``earth_radius_m + h_atmosphere_m``. The
    segment may be entirely inside, entirely outside, or cross the
    shell once. Returns the length of the in-shell portion.

    This is the correct path length to feed to
    ``physics/atmosphere.transmission``. Using the full geometric
    distance would apply a ground-level extinction coefficient to a
    vacuum path and underflow to zero (docs/ENCODER_PHYSICS_INTEGRATION.md,
    Decision 7).
    """
    r_outer = earth_radius_m + h_atmosphere_m

    def radius_squared(p: tuple[float, float, float]) -> float:
        return p[0] * p[0] + p[1] * p[1] + p[2] * p[2]

    source_inside = radius_squared(p_a) <= r_outer * r_outer
    target_inside = radius_squared(p_b) <= r_outer * r_outer

    if source_inside and target_inside:
        return range_m(p_a, p_b)
    if not source_inside and not target_inside:
        return 0.0

    if source_inside:
        p_inside, p_outside = p_a, p_b
    else:
        p_inside, p_outside = p_b, p_a

    dx = p_outside[0] - p_inside[0]
    dy = p_outside[1] - p_inside[1]
    dz = p_outside[2] - p_inside[2]
    a = dx * dx + dy * dy + dz * dz
    b = 2.0 * (p_inside[0] * dx + p_inside[1] * dy + p_inside[2] * dz)
    c = radius_squared(p_inside) - r_outer * r_outer

    if a <= 0.0:
        return 0.0

    disc = b * b - 4.0 * a * c
    if disc < 0.0:
        return range_m(p_a, p_b)

    sqrt_disc = math.sqrt(disc)
    t1 = (-b + sqrt_disc) / (2.0 * a)
    t2 = (-b - sqrt_disc) / (2.0 * a)
    positive_roots = [t for t in (t1, t2) if t > 0.0]
    if not positive_roots:
        return 0.0
    t_exit = min(min(positive_roots), 1.0)
    return float(t_exit * math.sqrt(a))


def visible_cap_half_angle_rad(
    r_source_m: float,
    r_target_m: float,
    *,
    earth_radius_m: float = EARTH_RADIUS_M,
) -> float:
    """Maximum angular separation between source and target subpoints
    such that the straight segment between them clears the Earth.

    Formula:

        theta_max = arccos(R / r_source) + arccos(R / r_target)

    where R is the Earth radius, r_source and r_target are the radial
    distances of the two endpoints from the Earth's centre. Both
    endpoints are assumed to be at or above R.

    Args:
        r_source_m: Radial distance of the source from the Earth's
            centre, in metres. Must be >= earth_radius_m.
        r_target_m: Radial distance of the target, in metres.
        earth_radius_m: Earth radius used for the calculation.

    Returns:
        Half-angle in radians, in [0, pi].
    """
    if r_source_m < earth_radius_m or r_target_m < earth_radius_m:
        raise ValueError(
            f"r_source_m and r_target_m must be >= earth_radius_m; got {r_source_m}, {r_target_m}"
        )
    cos_source = min(earth_radius_m / r_source_m, 1.0)
    cos_target = min(earth_radius_m / r_target_m, 1.0)
    return float(math.acos(cos_source) + math.acos(cos_target))


def sample_direction_in_visible_cap(
    lat_source_deg: float,
    lon_source_deg: float,
    half_angle_rad: float,
    rng: random.Random,
) -> tuple[float, float]:
    """Sample a direction uniformly on a spherical cap.

    The cap is centred on the source's subpoint direction and has the
    given half-angle. The returned (lat, lon) are the direction of a
    point on the unit sphere that is within ``half_angle_rad`` of the
    source direction. The point's radial distance is not part of the
    result; altitude is a separate parameter.

    Uniform sampling on the cap is achieved by sampling cos(theta)
    uniformly in [cos(half_angle), 1] and the azimuth uniformly in
    [0, 2*pi).

    Args:
        lat_source_deg: Latitude of the cap centre, in degrees.
        lon_source_deg: Longitude of the cap centre, in degrees.
        half_angle_rad: Cap half-angle in radians, in [0, pi].
        rng: Deterministic random source.

    Returns:
        (lat_deg, lon_deg) of a direction within the cap.
    """
    if not 0.0 <= half_angle_rad <= math.pi:
        raise ValueError(f"half_angle_rad must be in [0, pi]; got {half_angle_rad}")

    lat_s = math.radians(lat_source_deg)
    lon_s = math.radians(lon_source_deg)
    sx = math.cos(lat_s) * math.cos(lon_s)
    sy = math.cos(lat_s) * math.sin(lon_s)
    sz = math.sin(lat_s)

    cos_max = math.cos(half_angle_rad)
    cos_theta = cos_max + (1.0 - cos_max) * rng.random()
    cos_theta = max(-1.0, min(1.0, cos_theta))
    sin_theta = math.sqrt(max(0.0, 1.0 - cos_theta * cos_theta))
    phi = rng.uniform(0.0, 2.0 * math.pi)

    # Orthonormal tangent basis at the source direction.
    north = (0.0, 0.0, 1.0) if abs(sz) < 0.999 else (1.0, 0.0, 0.0)
    ex = north[1] * sz - north[2] * sy
    ey = north[2] * sx - north[0] * sz
    ez = north[0] * sy - north[1] * sx
    enorm = math.sqrt(ex * ex + ey * ey + ez * ez)
    ex, ey, ez = ex / enorm, ey / enorm, ez / enorm

    tx = sy * ez - sz * ey
    ty = sz * ex - sx * ez
    tz = sx * ey - sy * ex

    cx = math.cos(phi)
    sx_ = math.sin(phi)
    dx = cos_theta * sx + sin_theta * (cx * ex + sx_ * tx)
    dy = cos_theta * sy + sin_theta * (cx * ey + sx_ * ty)
    dz = cos_theta * sz + sin_theta * (cx * ez + sx_ * tz)

    lat_out = math.degrees(math.asin(max(-1.0, min(1.0, dz))))
    lon_out = math.degrees(math.atan2(dy, dx))
    return float(lat_out), float(lon_out)
