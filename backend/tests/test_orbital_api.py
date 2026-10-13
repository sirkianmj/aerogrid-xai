"""Tests for the orbital mechanics HTTP endpoints."""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)

# SGP4 propagation is only valid for a few weeks around the TLE epoch.
# The packaged ISS TLE has epoch 2014-01-20T22:23:04Z, so tests that
# propagate the ISS use times within a day of that epoch. Propagating
# a 2014 TLE to 2024 returns a position that is mathematically
# well-defined but physically meaningless: the ISS orbital elements
# have changed by many standard deviations in ten years.
ISS_T0 = "2014-01-20T22:00:00Z"
ISS_T1 = "2014-01-21T01:00:00Z"  # three hours, near epoch
ISS_DAY_START = "2014-01-20T22:23:04Z"
ISS_DAY_END = "2014-01-21T22:23:04Z"  # 24 hours

# The GEO test TLE has epoch 2024-01-01; its tests use that time.
GEO_T0 = "2024-01-01T00:00:00Z"
GEO_T1 = "2024-01-01T03:00:00Z"


# -- /orbital/satellites ---------------------------------------------------


def test_list_satellites_returns_three_keys() -> None:
    response = client.get("/orbital/satellites")
    assert response.status_code == 200
    payload = response.json()
    keys = sorted(s["key"] for s in payload["satellites"])
    assert keys == ["geo", "iss", "vanguard_r3"]


def test_list_satellites_entries_have_all_fields() -> None:
    response = client.get("/orbital/satellites")
    payload = response.json()
    for sat in payload["satellites"]:
        assert "name" in sat
        assert "epoch_utc" in sat
        assert sat["mean_motion_rev_per_day"] > 0
        assert sat["period_seconds"] > 0
        assert sat["orbit_class"] in {"LEO", "MEO", "GEO", "HEO"}


def test_list_satellites_classifies_iss_as_leo() -> None:
    response = client.get("/orbital/satellites")
    payload = response.json()
    iss = next(s for s in payload["satellites"] if s["key"] == "iss")
    assert iss["orbit_class"] == "LEO"


def test_list_satellites_classifies_geo_as_geo() -> None:
    response = client.get("/orbital/satellites")
    payload = response.json()
    geo = next(s for s in payload["satellites"] if s["key"] == "geo")
    assert geo["orbit_class"] == "GEO"


# -- /orbital/track --------------------------------------------------------


def test_track_returns_the_requested_number_of_points() -> None:
    response = client.get(
        "/orbital/track",
        params={
            "satellite": "iss",
            "t_start": ISS_T0,
            "t_end": ISS_T1,
            "step_seconds": 60.0,
        },
    )
    assert response.status_code == 200
    payload = response.json()
    # 3 hours at 60 s = 180 intervals, 181 points
    assert payload["n_points"] == 181
    assert len(payload["points"]) == 181


def test_track_points_change_over_time() -> None:
    """A LEO satellite moves; successive points differ in lat and lon."""
    response = client.get(
        "/orbital/track",
        params={
            "satellite": "iss",
            "t_start": ISS_T0,
            "t_end": ISS_T1,
            "step_seconds": 60.0,
        },
    )
    payload = response.json()
    points = payload["points"]
    lats = [p["lat_deg"] for p in points]
    assert len({round(x, 4) for x in lats}) > 10


def test_track_points_carry_the_eclipse_flag() -> None:
    response = client.get(
        "/orbital/track",
        params={
            "satellite": "iss",
            "t_start": ISS_T0,
            "t_end": ISS_T1,
            "step_seconds": 60.0,
        },
    )
    payload = response.json()
    for p in payload["points"]:
        assert isinstance(p["in_eclipse"], bool)
    # Over three hours a LEO satellite passes through eclipse at least once
    assert any(p["in_eclipse"] for p in payload["points"])


def test_track_rejects_unknown_satellite() -> None:
    # The endpoint rejects the unknown key before touching the time range,
    # so any valid ISO 8601 strings work here.
    response = client.get(
        "/orbital/track",
        params={
            "satellite": "nonexistent",
            "t_start": "2024-01-01T00:00:00Z",
            "t_end": "2024-01-01T03:00:00Z",
        },
    )
    assert response.status_code == 404
    assert "nonexistent" in response.json()["detail"]


def test_track_rejects_reversed_time_range() -> None:
    response = client.get(
        "/orbital/track",
        params={
            "satellite": "iss",
            "t_start": ISS_T1,
            "t_end": ISS_T0,
        },
    )
    assert response.status_code == 400
    assert "after" in response.json()["detail"]


def test_track_rejects_too_many_points() -> None:
    """A one-year range at 1 s step is above the 5000-point cap."""
    response = client.get(
        "/orbital/track",
        params={
            "satellite": "iss",
            "t_start": ISS_T0,
            "t_end": "2015-01-01T00:00:00Z",
            "step_seconds": 1.0,
        },
    )
    assert response.status_code == 400
    assert "5000" in response.json()["detail"]


def test_track_is_deterministic_across_requests() -> None:
    """SGP4 propagation is deterministic; the same query returns the
    same positions."""
    params: dict[str, str | float] = {
        "satellite": "iss",
        "t_start": ISS_T0,
        "t_end": "2014-01-20T22:30:00Z",
        "step_seconds": 60.0,
    }
    a = client.get("/orbital/track", params=params).json()
    b = client.get("/orbital/track", params=params).json()
    for pa, pb in zip(a["points"], b["points"], strict=True):
        assert pa["lat_deg"] == pb["lat_deg"]
        assert pa["lon_deg"] == pb["lon_deg"]
        assert pa["alt_m"] == pb["alt_m"]


# -- /orbital/visibility ---------------------------------------------------


def test_visibility_returns_windows_for_a_good_site() -> None:
    """Over 24 hours, the ISS passes over at least one mid-latitude site
    at least once."""
    response = client.get(
        "/orbital/visibility",
        params={
            "satellite": "iss",
            "ground_lat_deg": 40.0,
            "ground_lon_deg": -75.0,
            "t_start": ISS_DAY_START,
            "t_end": ISS_DAY_END,
            "step_seconds": 30.0,
            "min_elevation_deg": 10.0,
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["n_windows"] >= 1
    for w in payload["windows"]:
        assert w["duration_seconds"] > 0
        assert w["peak_elevation_deg"] >= 10.0


def test_visibility_rejects_unknown_satellite() -> None:
    # The endpoint rejects the unknown key before touching the time range,
    # so any valid ISO 8601 strings work here.
    response = client.get(
        "/orbital/visibility",
        params={
            "satellite": "nonexistent",
            "ground_lat_deg": 0.0,
            "ground_lon_deg": 0.0,
            "t_start": "2024-01-01T00:00:00Z",
            "t_end": "2024-01-01T03:00:00Z",
        },
    )
    assert response.status_code == 404


def test_visibility_rejects_reversed_time_range() -> None:
    response = client.get(
        "/orbital/visibility",
        params={
            "satellite": "iss",
            "ground_lat_deg": 0.0,
            "ground_lon_deg": 0.0,
            "t_start": ISS_T1,
            "t_end": ISS_T0,
        },
    )
    assert response.status_code == 400


def test_visibility_rejects_out_of_range_latitude() -> None:
    response = client.get(
        "/orbital/visibility",
        params={
            "satellite": "iss",
            "ground_lat_deg": 100.0,
            "ground_lon_deg": 0.0,
            "t_start": ISS_T0,
            "t_end": ISS_T1,
        },
    )
    assert response.status_code == 422


# -- Integration with the existing app -------------------------------------


def test_health_still_works() -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "healthy"}


def test_openapi_lists_orbital_routes() -> None:
    response = client.get("/openapi.json")
    assert response.status_code == 200
    paths = response.json()["paths"]
    assert "/orbital/satellites" in paths
    assert "/orbital/track" in paths
    assert "/orbital/visibility" in paths
    assert "get" in paths["/orbital/satellites"]


def test_control_router_still_registered() -> None:
    """The decisions router from Sprint 7 s7-4 is still present."""
    response = client.get("/openapi.json")
    paths = response.json()["paths"]
    assert "/decisions/charge" in paths
