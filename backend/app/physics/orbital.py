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
from datetime import UTC, datetime
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

    def at_utc(self, dt: datetime) -> StateVector:
        """Propagate to a UTC datetime and return the geodetic state."""
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=UTC)
        return self.at(_TS.from_datetime(dt))
