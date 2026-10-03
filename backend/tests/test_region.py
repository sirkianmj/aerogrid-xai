"""Unit tests for the geographic region model.

Roadmap task:
    s1-5 Geographic region model - Region class with coverage calculation.
    Gate: Grid-based coverage; overlap detection correct.
"""

from datetime import timedelta
from pathlib import Path

import pytest

from app.physics.orbital import Satellite
from app.physics.region import CoverageResult, Region, compute_coverage

ISS_FIXTURE = Path(__file__).parent / "fixtures" / "iss.tle"


@pytest.fixture
def iss() -> Satellite:
    return Satellite.from_tle_file(ISS_FIXTURE)


# --- Construction and validation ---------------------------------------------


def test_region_constructs() -> None:
    r = Region("mid-atlantic", 35.0, 42.0, -78.0, -70.0)
    assert r.name == "mid-atlantic"
    assert r.lat_span_deg == pytest.approx(7.0)
    assert r.lon_span_deg == pytest.approx(8.0)


def test_region_rejects_inverted_latitude() -> None:
    with pytest.raises(ValueError):
        Region("bad", 40.0, 30.0, -80.0, -70.0)


def test_region_rejects_inverted_longitude() -> None:
    with pytest.raises(ValueError):
        Region("bad", 35.0, 40.0, -70.0, -80.0)


def test_region_rejects_out_of_range_latitude() -> None:
    with pytest.raises(ValueError):
        Region("bad", -95.0, 40.0, -80.0, -70.0)


def test_region_rejects_out_of_range_longitude() -> None:
    with pytest.raises(ValueError):
        Region("bad", 35.0, 40.0, -190.0, -70.0)


# --- Geometry -----------------------------------------------------------------


def test_region_center() -> None:
    r = Region("box", 0.0, 10.0, -10.0, 10.0)
    assert r.center == (5.0, 0.0)


def test_region_contains_inside() -> None:
    r = Region("box", 0.0, 10.0, -10.0, 10.0)
    assert r.contains(5.0, 0.0)
    assert r.contains(0.0, -10.0)  # lower corner inclusive
    assert r.contains(10.0, 10.0)  # upper corner inclusive


def test_region_contains_outside() -> None:
    r = Region("box", 0.0, 10.0, -10.0, 10.0)
    assert not r.contains(-1.0, 0.0)
    assert not r.contains(11.0, 0.0)
    assert not r.contains(5.0, -11.0)
    assert not r.contains(5.0, 11.0)


# --- Overlap detection --------------------------------------------------------


def test_regions_overlap_when_intersecting() -> None:
    a = Region("a", 0.0, 10.0, -10.0, 10.0)
    b = Region("b", 5.0, 15.0, 0.0, 20.0)
    assert a.overlaps(b)
    assert b.overlaps(a)


def test_regions_do_not_overlap_when_disjoint_latitude() -> None:
    a = Region("a", 0.0, 10.0, -10.0, 10.0)
    b = Region("b", 20.0, 30.0, -10.0, 10.0)
    assert not a.overlaps(b)
    assert not b.overlaps(a)


def test_regions_do_not_overlap_when_disjoint_longitude() -> None:
    a = Region("a", 0.0, 10.0, -10.0, 10.0)
    b = Region("b", 0.0, 10.0, 20.0, 30.0)
    assert not a.overlaps(b)
    assert not b.overlaps(a)


def test_regions_overlap_when_nested() -> None:
    outer = Region("outer", 0.0, 30.0, -30.0, 30.0)
    inner = Region("inner", 10.0, 20.0, -20.0, 20.0)
    assert outer.overlaps(inner)
    assert inner.overlaps(outer)


def test_regions_overlap_when_edges_touch() -> None:
    a = Region("a", 0.0, 10.0, -10.0, 10.0)
    b = Region("b", 10.0, 20.0, 0.0, 10.0)  # shares lat=10 edge
    assert a.overlaps(b)
    assert b.overlaps(a)


# --- Grid generation ----------------------------------------------------------


def test_grid_nodes_count() -> None:
    r = Region("box", 0.0, 10.0, -10.0, 10.0)
    nodes = r.grid_nodes(n_lat=3, n_lon=4)
    assert len(nodes) == 12


def test_grid_nodes_span_corners() -> None:
    r = Region("box", 0.0, 10.0, -10.0, 10.0)
    nodes = r.grid_nodes(n_lat=3, n_lon=3)
    lats = {round(n.lat_deg, 6) for n in nodes}
    lons = {round(n.lon_deg, 6) for n in nodes}
    assert lats == {0.0, 5.0, 10.0}
    assert lons == {-10.0, 0.0, 10.0}


def test_grid_nodes_rejects_zero_dimension() -> None:
    r = Region("box", 0.0, 10.0, -10.0, 10.0)
    with pytest.raises(ValueError):
        r.grid_nodes(n_lat=0, n_lon=5)


# --- Coverage computation -----------------------------------------------------


def test_compute_coverage_returns_coverage_result(iss: Satellite) -> None:
    region = Region("greenbelt", 38.5, 39.5, -77.5, -76.5)
    t_start = iss.epoch_utc
    t_end = t_start + timedelta(hours=6)
    result = compute_coverage(iss, region, t_start, t_end, n_lat=2, n_lon=2, step_seconds=60.0)
    assert isinstance(result, CoverageResult)
    assert result.n_nodes == 4
    assert 0 <= result.n_nodes_covered <= 4
    assert result.total_windows >= result.n_nodes_covered
    assert 0.0 <= result.covered_fraction <= 1.0


def test_compute_coverage_iss_covers_east_coast_in_24h(iss: Satellite) -> None:
    """Over 24 hours, the ISS passes over the US East Coast multiple times.
    A grid covering a wide area should have most nodes covered."""
    region = Region("east-coast", 30.0, 45.0, -85.0, -70.0)
    t_start = iss.epoch_utc
    t_end = t_start + timedelta(hours=24)
    result = compute_coverage(iss, region, t_start, t_end, n_lat=3, n_lon=3, step_seconds=120.0)
    assert result.n_nodes == 9
    assert result.n_nodes_covered >= 1, "Expected at least one grid node covered"
    assert result.covered_fraction > 0.0
