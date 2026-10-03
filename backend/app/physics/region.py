"""Geographic region model with grid-based coverage calculation.

Reference:
    AeroGrid-XAI Final Comprehensive Specification (Rev. 6), Section 11
    "Geographic Coverage".

The Region class represents an axis-aligned geographic bounding box.
Coverage is computed on a rectangular grid of GroundNodes using the
topocentric visibility-window primitive from app.physics.orbital.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from app.physics.orbital import GroundNode, Satellite, visibility_windows


def _linspace(start: float, stop: float, n: int) -> list[float]:
    """Return n evenly spaced floats from start to stop, inclusive."""
    if n == 1:
        return [(start + stop) / 2.0]
    step = (stop - start) / (n - 1)
    return [start + i * step for i in range(n)]


@dataclass(frozen=True)
class Region:
    """An axis-aligned geographic region on the WGS-84 ellipsoid."""

    name: str
    lat_min_deg: float
    lat_max_deg: float
    lon_min_deg: float
    lon_max_deg: float

    def __post_init__(self) -> None:
        if not -90.0 <= self.lat_min_deg <= 90.0:
            raise ValueError(f"lat_min_deg out of range: {self.lat_min_deg}")
        if not -90.0 <= self.lat_max_deg <= 90.0:
            raise ValueError(f"lat_max_deg out of range: {self.lat_max_deg}")
        if not -180.0 <= self.lon_min_deg <= 180.0:
            raise ValueError(f"lon_min_deg out of range: {self.lon_min_deg}")
        if not -180.0 <= self.lon_max_deg <= 180.0:
            raise ValueError(f"lon_max_deg out of range: {self.lon_max_deg}")
        if self.lat_min_deg >= self.lat_max_deg:
            raise ValueError(
                f"lat_min_deg ({self.lat_min_deg}) must be < lat_max_deg ({self.lat_max_deg})"
            )
        if self.lon_min_deg >= self.lon_max_deg:
            raise ValueError(
                f"lon_min_deg ({self.lon_min_deg}) must be < lon_max_deg ({self.lon_max_deg})"
            )

    @property
    def lat_span_deg(self) -> float:
        return self.lat_max_deg - self.lat_min_deg

    @property
    def lon_span_deg(self) -> float:
        return self.lon_max_deg - self.lon_min_deg

    @property
    def center(self) -> tuple[float, float]:
        lat = (self.lat_min_deg + self.lat_max_deg) / 2.0
        lon = (self.lon_min_deg + self.lon_max_deg) / 2.0
        return (lat, lon)

    def contains(self, lat_deg: float, lon_deg: float) -> bool:
        """Return True if the point lies inside the region (inclusive)."""
        return (
            self.lat_min_deg <= lat_deg <= self.lat_max_deg
            and self.lon_min_deg <= lon_deg <= self.lon_max_deg
        )

    def overlaps(self, other: Region) -> bool:
        """Return True if the two regions' bounding boxes intersect.

        Two regions overlap if their latitude ranges overlap AND their
        longitude ranges overlap. Boxes that merely touch at an edge or
        corner are considered overlapping (closed intervals).
        """
        return (
            self.lat_max_deg >= other.lat_min_deg
            and other.lat_max_deg >= self.lat_min_deg
            and self.lon_max_deg >= other.lon_min_deg
            and other.lon_max_deg >= self.lon_min_deg
        )

    def grid_nodes(self, n_lat: int, n_lon: int, alt_m: float = 0.0) -> tuple[GroundNode, ...]:
        """Return a rectangular grid of GroundNodes covering the region.

        The grid has n_lat rows (latitude) and n_lon columns (longitude),
        inclusive of both boundaries. GroundNode names are of the form
        ``{region.name}_g{i}_{j}``.
        """
        if n_lat < 1 or n_lon < 1:
            raise ValueError(f"grid dimensions must be >= 1; got {n_lat}x{n_lon}")
        lats = _linspace(self.lat_min_deg, self.lat_max_deg, n_lat)
        lons = _linspace(self.lon_min_deg, self.lon_max_deg, n_lon)
        return tuple(
            GroundNode(
                name=f"{self.name}_g{i}_{j}",
                lat_deg=lat,
                lon_deg=lon,
                alt_m=alt_m,
            )
            for i, lat in enumerate(lats)
            for j, lon in enumerate(lons)
        )


@dataclass(frozen=True)
class CoverageResult:
    """The coverage of a region by a satellite over a time interval."""

    region: Region
    n_nodes: int
    n_nodes_covered: int
    total_windows: int

    @property
    def covered_fraction(self) -> float:
        if self.n_nodes == 0:
            return 0.0
        return self.n_nodes_covered / self.n_nodes


def compute_coverage(
    sat: Satellite,
    region: Region,
    t_start: datetime,
    t_end: datetime,
    n_lat: int = 5,
    n_lon: int = 5,
    step_seconds: float = 60.0,
    min_elevation_deg: float = 10.0,
) -> CoverageResult:
    """Grid-based coverage of a region by a satellite over a time range.

    For each GroundNode in the region's grid, compute visibility windows
    over the interval. A node is considered covered if it has at least
    one visibility window.
    """
    nodes = region.grid_nodes(n_lat=n_lat, n_lon=n_lon)
    covered = 0
    total_windows = 0
    for node in nodes:
        windows = visibility_windows(
            sat,
            node,
            t_start,
            t_end,
            step_seconds=step_seconds,
            min_elevation_deg=min_elevation_deg,
        )
        if windows:
            covered += 1
            total_windows += len(windows)
    return CoverageResult(
        region=region,
        n_nodes=len(nodes),
        n_nodes_covered=covered,
        total_windows=total_windows,
    )
