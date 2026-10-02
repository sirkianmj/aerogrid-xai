"""Unit tests for the health endpoint."""

from fastapi.testclient import TestClient

from api.main import app

client = TestClient(app)


def test_health_returns_200() -> None:
    response = client.get("/health")
    assert response.status_code == 200


def test_health_payload() -> None:
    response = client.get("/health")
    assert response.json() == {"status": "healthy"}


def test_metrics_endpoint_exists() -> None:
    response = client.get("/metrics")
    assert response.status_code == 200
