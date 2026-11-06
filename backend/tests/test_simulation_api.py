"""Tests for POST /simulation/run.

Covers response schema, sample counts per preset, per-sample epistemic
tags, cumulative energy monotonicity, error handling, and router
registration. Each test uses the 10-minute preset (11 samples) to keep
the suite under ~15 s wall-clock.
"""

from __future__ import annotations

import itertools

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def _base_req(**overrides: object) -> dict[str, object]:
    req: dict[str, object] = {
        "preset": "10min",
        "seed": 1,
        "satellite_key": "iss",
        "n_uavs": 4,
    }
    req.update(overrides)
    return req


def test_run_returns_200_with_expected_fields() -> None:
    r = client.post("/simulation/run", json=_base_req())
    assert r.status_code == 200
    body = r.json()
    for key in (
        "epistemic_tag",
        "preset",
        "duration_s",
        "step_s",
        "n_samples",
        "config_summary",
        "warnings",
        "samples",
    ):
        assert key in body, key
    assert body["epistemic_tag"] == "simulation_result"
    assert len(body["samples"]) == body["n_samples"]


def test_sample_count_matches_duration() -> None:
    """10-minute preset at 60 s step -> 600 s / 60 s + 1 = 11 samples."""
    r = client.post("/simulation/run", json=_base_req())
    body = r.json()
    assert body["n_samples"] == 11
    assert abs(body["duration_s"] - 600.0) < 1.0
    assert abs(body["step_s"] - 60.0) < 1.0


def test_every_sample_has_epistemic_tag() -> None:
    r = client.post("/simulation/run", json=_base_req())
    body = r.json()
    for sample in body["samples"]:
        assert sample["epistemic_tag"] == "simulation_result"


def test_cumulative_energy_monotonic() -> None:
    r = client.post("/simulation/run", json=_base_req())
    body = r.json()
    energies = [s["cumulative_energy_j"] for s in body["samples"]]
    assert energies[0] == 0.0
    for a, b in itertools.pairwise(energies):
        assert b >= a - 1e-9, f"cumulative energy decreased: {a} -> {b}"


def test_samples_carry_uav_breakdown() -> None:
    r = client.post("/simulation/run", json=_base_req(n_uavs=4))
    body = r.json()
    for sample in body["samples"]:
        assert len(sample["uavs"]) == 4
        for u in sample["uavs"]:
            assert "received_power_w" in u
            assert "delivered_power_w" in u
            assert "thermal_headroom_c" in u


def test_invalid_step_returns_422() -> None:
    r = client.post("/simulation/run", json=_base_req(step_s=0.5))
    assert r.status_code == 422


def test_custom_preset_respects_duration() -> None:
    r = client.post(
        "/simulation/run",
        json=_base_req(preset="custom", duration_s=1800.0, step_s=60.0),
    )
    assert r.status_code == 200
    body = r.json()
    # 1800 s / 60 s + 1 = 31 samples
    assert body["n_samples"] == 31
    assert abs(body["duration_s"] - 1800.0) < 1.0


def test_router_registered_in_openapi() -> None:
    r = client.get("/openapi.json")
    assert r.status_code == 200
    paths = r.json()["paths"]
    assert "/simulation/run" in paths
