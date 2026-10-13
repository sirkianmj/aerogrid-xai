"""Tests for the telemetry WebSocket endpoint."""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_stream_sends_one_snapshot_immediately() -> None:
    """The first snapshot arrives without waiting for the interval."""
    with client.websocket_connect(
        "/telemetry/stream?satellite=vanguard_r3&interval_seconds=2.0"
    ) as ws:
        payload = ws.receive_json()
    assert payload["epistemic_tag"] == "simulation_result"
    assert payload["sequence"] == 0
    assert payload["satellite"]["key"] == "vanguard_r3"
    assert payload["satellite"]["orbit_class"] in {"LEO", "MEO", "GEO", "HEO"}


def test_stream_snapshot_has_all_fields() -> None:
    with client.websocket_connect(
        "/telemetry/stream?satellite=vanguard_r3&interval_seconds=2.0"
    ) as ws:
        payload = ws.receive_json()
    assert "time_utc" in payload
    orbital = payload["orbital"]
    for field in ("lat_deg", "lon_deg", "alt_m", "speed_km_s", "in_eclipse"):
        assert field in orbital
    thermal = payload["thermal"]
    for field in (
        "t_plc_k",
        "t_plc_c",
        "t_te_k",
        "t_te_c",
        "thermal_runaway_power_w",
        "safety_margin_w",
    ):
        assert field in thermal


def test_stream_latitude_and_longitude_are_in_bounds() -> None:
    with client.websocket_connect(
        "/telemetry/stream?satellite=vanguard_r3&interval_seconds=2.0"
    ) as ws:
        payload = ws.receive_json()
    orbital = payload["orbital"]
    assert -90.0 <= orbital["lat_deg"] <= 90.0
    assert -180.0 <= orbital["lon_deg"] <= 180.0
    assert orbital["alt_m"] > 0.0
    assert orbital["speed_km_s"] > 0.0


def test_stream_second_snapshot_advances_sequence() -> None:
    """The second snapshot has sequence 1. Uses a short interval so the
    test does not sit idle for the default 2 seconds."""
    with client.websocket_connect(
        "/telemetry/stream?satellite=vanguard_r3&interval_seconds=0.1"
    ) as ws:
        first = ws.receive_json()
        second = ws.receive_json()
    assert first["sequence"] == 0
    assert second["sequence"] == 1


def test_stream_snapshots_advance_in_time() -> None:
    """Two consecutive snapshots have different propagated times."""
    with client.websocket_connect(
        "/telemetry/stream?satellite=vanguard_r3&interval_seconds=0.1"
    ) as ws:
        a = ws.receive_json()
        b = ws.receive_json()
    assert a["time_utc"] != b["time_utc"]


def test_stream_unknown_satellite_closes_with_4404() -> None:
    """An unknown satellite key is rejected before any snapshot is sent."""
    from starlette.websockets import WebSocketDisconnect

    try:
        with client.websocket_connect(
            "/telemetry/stream?satellite=nonexistent&interval_seconds=2.0"
        ) as ws:
            ws.receive_json()
        raise AssertionError("expected the connection to close")
    except WebSocketDisconnect as exc:
        assert exc.code == 4404


def test_stream_bad_interval_too_small_closes_with_4400() -> None:
    from starlette.websockets import WebSocketDisconnect

    try:
        with client.websocket_connect(
            "/telemetry/stream?satellite=vanguard_r3&interval_seconds=0.01"
        ) as ws:
            ws.receive_json()
        raise AssertionError("expected the connection to close")
    except WebSocketDisconnect as exc:
        assert exc.code == 4400


def test_stream_bad_interval_too_large_closes_with_4400() -> None:
    from starlette.websockets import WebSocketDisconnect

    try:
        with client.websocket_connect(
            "/telemetry/stream?satellite=vanguard_r3&interval_seconds=120.0"
        ) as ws:
            ws.receive_json()
        raise AssertionError("expected the connection to close")
    except WebSocketDisconnect as exc:
        assert exc.code == 4400


def test_stream_default_satellite_and_interval_work() -> None:
    """With no query parameters the defaults apply."""
    with client.websocket_connect("/telemetry/stream") as ws:
        payload = ws.receive_json()
    assert payload["satellite"]["key"] == "vanguard_r3"


def test_health_still_works() -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "healthy"}


def test_openapi_lists_existing_http_routes() -> None:
    """The WebSocket endpoint is not in the OpenAPI document (OpenAPI
    does not model WebSockets), but the HTTP routers are."""
    response = client.get("/openapi.json")
    paths = response.json()["paths"]
    assert "/decisions/charge" in paths
    assert "/orbital/satellites" in paths
    assert "/digital-twin/state" in paths
