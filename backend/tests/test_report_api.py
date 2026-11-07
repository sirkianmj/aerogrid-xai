"""Tests for POST /report/generate.

The endpoint returns binary PDF; assertions are structural (PDF magic
bytes, content-type, content-disposition) plus robustness against
missing and malformed step_outputs. The visual PDF layout is verified
by the user opening the file, not by these tests.
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def _payload_full() -> dict[str, object]:
    return {
        "mission_config": {
            "seed": 20261014,
            "satellite_key": "iss",
            "n_uavs": 4,
            "transmitter_power_w": 10000.0,
            "wavelength_nm": 1064.0,
        },
        "step_outputs": {
            "3": {
                "step": 3,
                "data": {"population_size": 8, "n_generations": 3, "discovered": []},
                "at": 1700000000000,
            },
            "5": {
                "step": 5,
                "data": {
                    "preset": "10min",
                    "duration_s": 600,
                    "n_samples": 3,
                    "warnings": [],
                    "samples": [
                        {"elapsed_s": 0, "delivered_power_w": 10},
                        {"elapsed_s": 60, "delivered_power_w": 12},
                        {"elapsed_s": 120, "delivered_power_w": 11},
                    ],
                },
                "at": 1700000000001,
            },
        },
        "mission_state": None,
    }


def test_returns_pdf() -> None:
    r = client.post("/report/generate", json=_payload_full())
    assert r.status_code == 200
    assert r.headers["content-type"] == "application/pdf"
    assert r.content.startswith(b"%PDF-")
    assert len(r.content) > 1000


def test_content_disposition_header() -> None:
    r = client.post("/report/generate", json=_payload_full())
    assert "attachment; filename=" in r.headers["content-disposition"]
    assert "aerogrid-report.pdf" in r.headers["content-disposition"]


def test_empty_payload_ok() -> None:
    r = client.post("/report/generate", json={})
    assert r.status_code == 200
    assert r.content.startswith(b"%PDF-")


def test_missing_steps_render_gracefully() -> None:
    payload = {
        "mission_config": {"seed": 1},
        "step_outputs": {
            "3": {"step": 3, "data": {"population_size": 4}, "at": 0},
        },
    }
    r = client.post("/report/generate", json=payload)
    assert r.status_code == 200
    assert r.content.startswith(b"%PDF-")


def test_malformed_step_data_does_not_crash() -> None:
    payload = {
        "mission_config": {"seed": 1},
        "step_outputs": {
            "5": {"step": 5, "data": "garbage", "at": 0},
        },
    }
    r = client.post("/report/generate", json=payload)
    assert r.status_code == 200


def test_invalid_payload_returns_422() -> None:
    r = client.post("/report/generate", json={"step_outputs": [1, 2, 3]})
    assert r.status_code == 422


def test_router_registered_in_openapi() -> None:
    r = client.get("/openapi.json")
    assert r.status_code == 200
    assert "/report/generate" in r.json()["paths"]
