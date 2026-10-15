"""The /status endpoint reports dependency health.

The tests do not require every dependency to be healthy; they check the
shape of the response and that the endpoint always returns 200.
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_status_always_returns_200() -> None:
    r = client.get("/status")
    assert r.status_code == 200


def test_status_payload_shape() -> None:
    r = client.get("/status")
    body = r.json()
    assert "overall" in body
    assert body["overall"] in {"ok", "degraded", "down"}
    assert "checked_at" in body
    assert isinstance(body["dependencies"], list)
    names = {d["name"] for d in body["dependencies"]}
    assert names == {"postgres", "redis", "prometheus", "grafana"}


def test_postgres_down_means_overall_down() -> None:
    """Postgres is a hard dependency. Its failure cannot be `degraded`."""
    r = client.get("/status")
    body = r.json()
    pg = next(d for d in body["dependencies"] if d["name"] == "postgres")
    if pg["status"] == "ok":
        assert body["overall"] in {"ok", "degraded"}
    else:
        assert body["overall"] == "down"


def test_status_includes_latency() -> None:
    r = client.get("/status")
    for d in r.json()["dependencies"]:
        assert isinstance(d["latency_ms"], (int, float))
        assert d["latency_ms"] >= 0.0
