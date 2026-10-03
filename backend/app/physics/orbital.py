"""Orbital mechanics via Skyfield SGP4/SDP4 propagation.

Reference:
    AeroGrid-XAI Final Comprehensive Specification (Rev. 6), Section 7.1
    "Orbital Mechanics (Required)".

All satellite state is time-varying. This module never returns a hard-coded
position: every call to ``Satellite.at()`` or ``Satellite.at_utc()`` runs the
SGP4/SDP4 propagator over the TLE.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import cast

import numpy as np
from skyfield.api import EarthSatellite, load, wgs84  # type: ignore[import-untyped]
from skyfield.timelib import Time  # type: ignore[import-untyped]

_TS = load.timescale()

LEO_MAX_ALT_KM = 2_000.0
GEO_ALT_KM = 35_786.0
GEO_TOLERANCE_KM = 500.0


def classify_orbit(alt_km: float) -> str:
    """Classify an orbit by altitude band.

    Returns one of "LEO", "MEO", "GEO", "HEO". "HEO" is reserved for
    altitudes above the MEO band (including highly elliptical orbits when
    sampled near apogee).
    """
    if alt_km < 0:
        raise ValueError(f"Altitude must be non-negative; got {alt_km}")
    if alt_km <= LEO_MAX_ALT_KM:
        return "LEO"
    if abs(alt_km - GEO_ALT_KM) <= GEO_TOLERANCE_KM:
        return "GEO"
    if alt_km < GEO_ALT_KM:
        return "MEO"
    return "HEO"


@dataclass(frozen=True)
class StateVector:
    """A time-stamped satellite state in the geodetic frame."""

    time_utc: datetime
    lat_deg: float
    lon_deg: float
    alt_m: float
    speed_km_s: float

    @property
    def alt_km(self) -> float:
        return self.alt_m / 1000.0


class Satellite:
    """A satellite whose position is propagated by SGP4/SDP4.

    The state is a function of time only. Calling ``at()`` with the same
    time always yields the same state, and calling it with different times
    yields different states (within the SGP4 validity window around the
    TLE epoch).
    """

    def __init__(self, name: str, line1: str, line2: str) -> None:
        self.name = name
        self.line1 = line1
        self.line2 = line2
        self._earth_sat = EarthSatellite(line1, line2, name, _TS)

    @classmethod
    def from_tle_file(cls, path: Path | str) -> Satellite:
        """Load the first TLE from a local file (name, line1, line2)."""
        lines = [ln.strip() for ln in Path(path).read_text().splitlines() if ln.strip()]
        if len(lines) < 3:
            raise ValueError(f"TLE file must contain at least 3 non-empty lines; got {len(lines)}")
        return cls(lines[0], lines[1], lines[2])

    @property
    def epoch_utc(self) -> datetime:
        """The TLE epoch as a timezone-aware UTC datetime."""
        return cast("datetime", self._earth_sat.epoch.utc_datetime())

    @property
    def mean_motion_rev_per_day(self) -> float:
        """Mean motion from the TLE, in revolutions per day."""
        return float(self._earth_sat.model.no_kozai * 1440.0 / (2.0 * np.pi))

    @property
    def period_seconds(self) -> float:
        """Orbital period derived from the TLE mean motion."""
        return 86_400.0 / self.mean_motion_rev_per_day

    def at(self, t: Time) -> StateVector:
        """Propagate to a Skyfield Time and return the geodetic state."""
        geocentric = self._earth_sat.at(t)
        subpoint = wgs84.subpoint(geocentric)
        speed_km_s = float(np.linalg.norm(geocentric.velocity.km_per_s))
        return StateVector(
            time_utc=t.utc_datetime(),
            lat_deg=float(subpoint.latitude.degrees),
            lon_deg=float(subpoint.longitude.degrees),
            alt_m=float(subpoint.elevation.m),
            speed_km_s=speed_km_s,
        )

    def geocentric_position_km(self, t: Time) -> np.ndarray:
        """Geocentric position in the GCRS frame, km."""
        return np.asarray(self._earth_sat.at(t).position.km, dtype=float)

    def is_in_eclipse(self, t: Time) -> bool:
        """True if the satellite is in Earth's umbra at time t.

        Uses the cylindrical shadow approximation: the satellite is in
        eclipse when its geocentric position has a negative projection on
        the Sun direction and its perpendicular distance from that line
        is less than Earth's mean radius.
        """
        r_sat = self.geocentric_position_km(t)
        r_sun = sun_position_eci_km(t)
        s_hat = r_sun / float(np.linalg.norm(r_sun))
        d = float(np.dot(r_sat, s_hat))
        if d > 0.0:
            return False
        perp = r_sat - d * s_hat
        return float(np.linalg.norm(perp)) < R_EARTH_KM

    def is_in_eclipse_conical(self, t: Time) -> bool:
        """True if the satellite is in Earth's umbra at time t, using the
        conical (finite angular size of the Sun) shadow model of Vallado,
        "Fundamentals of Astrodynamics and Applications", 4th ed., Ch. 5.

        The umbra is a cone with apex beyond Earth. At distance d from
        Earth centre along the anti-Sun axis, the umbra radius is
        R_E - d * tan(theta_sun), where theta_sun is the Sun's angular
        radius as seen from Earth (approximately 0.00465 rad).

        This model is more conservative than the cylindrical model: it
        declares eclipse only for the fully shadowed region.
        """
        r_sat = self.geocentric_position_km(t)
        r_sun = sun_position_eci_km(t)
        s_hat = r_sun / float(np.linalg.norm(r_sun))

        d_along = float(np.dot(r_sat, s_hat))
        if d_along > 0.0:
            return False

        perp = r_sat - d_along * s_hat
        h = float(np.linalg.norm(perp))

        # Distance along the anti-Sun axis from Earth centre.
        d = -d_along
        theta_sun_rad = 0.00465
        umbra_radius_km = R_EARTH_KM - d * float(np.tan(theta_sun_rad))
        if umbra_radius_km <= 0.0:
            return False
        return h < umbra_radius_km

    def look_angle(self, node: GroundNode, t: Time) -> LookAngle:
        """Topocentric look angles from a ground node at time t."""
        observer = wgs84.latlon(node.lat_deg, node.lon_deg, elevation_m=node.alt_m)
        difference = self._earth_sat - observer
        alt, az, distance = difference.at(t).altaz()
        return LookAngle(
            time_utc=t.utc_datetime(),
            elevation_deg=float(alt.degrees),
            azimuth_deg=float(az.degrees),
            range_km=float(distance.km),
        )

    def at_utc(self, dt: datetime) -> StateVector:
        """Propagate to a UTC datetime and return the geodetic state."""
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=UTC)
        return self.at(_TS.from_datetime(dt))


# --- Topocentric look angles and visibility (s1-3) -------------------------

R_EARTH_KM = 6371.0
AU_KM = 149_597_870.7


@dataclass(frozen=True)
class GroundNode:
    """A ground station or fixed ground reference point."""

    name: str
    lat_deg: float
    lon_deg: float
    alt_m: float = 0.0


@dataclass(frozen=True)
class LookAngle:
    """Topocentric look angles from a ground node to a satellite."""

    time_utc: datetime
    elevation_deg: float
    azimuth_deg: float
    range_km: float


@dataclass(frozen=True)
class VisibilityWindow:
    """A contiguous interval during which a satellite is above a minimum
    elevation as seen from a ground node."""

    start_utc: datetime
    end_utc: datetime
    peak_elevation_deg: float
    peak_time_utc: datetime

    @property
    def duration_seconds(self) -> float:
        return (self.end_utc - self.start_utc).total_seconds()


def sun_position_eci_km(t: Time) -> np.ndarray:
    """Low-precision analytic Sun position in ECI (J2000), km.

    Uses the Astronomical Almanac low-precision formulas (accurate to
    ~0.01 deg in ecliptic longitude, sufficient for eclipse detection).
    """
    jd_tt = float(t.tt)
    n = jd_tt - 2_451_545.0
    big_l = np.radians(280.460 + 0.9856474 * n)
    g = np.radians(357.528 + 0.9856003 * n)
    lam = big_l + np.radians(1.915) * np.sin(g) + np.radians(0.020) * np.sin(2.0 * g)
    eps = np.radians(23.439 - 0.0000004 * n)
    vec = np.array(
        [
            np.cos(lam),
            np.cos(eps) * np.sin(lam),
            np.sin(eps) * np.sin(lam),
        ],
        dtype=float,
    )
    r_au = 1.00014 - 0.01671 * np.cos(g) - 0.00014 * np.cos(2.0 * g)
    return np.asarray(vec * r_au * AU_KM, dtype=float)


def visibility_windows(
    sat: Satellite,
    node: GroundNode,
    t_start: datetime,
    t_end: datetime,
    step_seconds: float = 30.0,
    min_elevation_deg: float = 5.0,
) -> tuple[VisibilityWindow, ...]:
    """Compute visibility windows for a satellite from a ground node.

    A window opens when elevation first rises above min_elevation_deg and
    closes when it next drops below. Windows are sorted by start time and
    non-overlapping.
    """
    if step_seconds <= 0.0:
        raise ValueError(f"step_seconds must be > 0; got {step_seconds}")
    if t_end <= t_start:
        raise ValueError("t_end must be strictly after t_start")
    if t_start.tzinfo is None:
        t_start = t_start.replace(tzinfo=UTC)
    if t_end.tzinfo is None:
        t_end = t_end.replace(tzinfo=UTC)

    times: list[datetime] = []
    elevations: list[float] = []
    t = t_start
    dt = timedelta(seconds=step_seconds)
    while t <= t_end:
        times.append(t)
        elevations.append(sat.look_angle(node, _TS.from_datetime(t)).elevation_deg)
        t = t + dt

    windows: list[VisibilityWindow] = []
    i = 0
    n = len(times)
    while i < n:
        if elevations[i] < min_elevation_deg:
            i += 1
            continue
        start_idx = i
        while i < n and elevations[i] >= min_elevation_deg:
            i += 1
        end_idx = i - 1
        # A visibility window is a physical pass, not a single sampling
        # point. A one-sample window means elevation only crossed the
        # threshold at one instant; this is a grazing pass and not a real
        # visibility interval. Skip it.
        if end_idx == start_idx:
            continue
        peak_idx = max(range(start_idx, end_idx + 1), key=lambda j: elevations[j])
        windows.append(
            VisibilityWindow(
                start_utc=times[start_idx],
                end_utc=times[end_idx],
                peak_elevation_deg=elevations[peak_idx],
                peak_time_utc=times[peak_idx],
            )
        )
    return tuple(windows)


def _add_look_angle_and_eclipse() -> None:
    """Marker to keep the append clean; not called."""
