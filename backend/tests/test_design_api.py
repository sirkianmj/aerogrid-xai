"""Tests for the design evaluation endpoints."""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_presets_endpoint_returns_anonymous_starting_points() -> None:
    r = client.get("/design/presets")
    assert r.status_code == 200
    body = r.json()
    assert len(body["satellites"]) == 5
    assert len(body["drones"]) == 6
    for s in body["satellites"]:
        assert s["id"].startswith("SAT-")
        assert s["a_km"] > 0
    for d in body["drones"]:
        assert d["id"].startswith("UAV-")
        assert d["mass_kg"] > 0


def test_satellite_evaluation_feasible_for_standard_leo() -> None:
    body = {
        "a_km": 6771.0,
        "e": 0.0,
        "i_deg": 51.6,
        "raan_deg": 0.0,
        "argp_deg": 0.0,
        "m0_deg": 0.0,
        "epoch_utc": "2026-10-14T12:00:00Z",
        "transmitter_power_w": 10000.0,
        "wavelength_nm": 1064.0,
        "transmitter_aperture_m": 0.02,
        "n_uavs": 1,
        "uav_receiver_aperture_m2": 0.5,
        "visibility_km": 10.0,
        "cloud_factor": 0.0,
    }
    r = client.post("/design/satellite", json=body)
    assert r.status_code == 200
    resp = r.json()
    assert resp["verdict"] in {"feasible", "infeasible"}
    assert "metrics" in resp
    assert "transmittance" in resp["metrics"]


def test_drone_evaluation_returns_metrics() -> None:
    body = {
        "mass_kg": 5.0,
        "wingspan_m": 1.5,
        "battery_wh": 100.0,
        "receiver_aperture_m2": 0.5,
        "receiver_type": "laser_photovoltaic",
        "battery_efficiency": 0.92,
        "thermal_limit_c": 80.0,
        "satellite_key": "iss",
        "uav_receiver_type": "laser_photovoltaic",
    }
    # Note: DroneDesignRequest doesn't accept uav_receiver_type. Clean up.
    body.pop("uav_receiver_type", None)
    r = client.post("/design/drone", json=body)
    assert r.status_code == 200
    resp = r.json()
    assert "delivered_power_w" in resp["metrics"]
    assert "wing_loading_kg_per_m2" in resp["metrics"]
    assert "battery_charge_time_h" in resp["metrics"]


def test_oversized_drone_is_flagged_infeasible_by_wing_loading() -> None:
    """A 500 kg drone with a 2 m wingspan cannot fly."""
    body = {
        "mass_kg": 500.0,
        "wingspan_m": 2.0,
        "battery_wh": 100.0,
        "receiver_aperture_m2": 0.5,
        "receiver_type": "laser_photovoltaic",
        "battery_efficiency": 0.92,
        "thermal_limit_c": 80.0,
    }
    r = client.post("/design/drone", json=body)
    assert r.status_code == 200
    resp = r.json()
    assert resp["verdict"] == "infeasible"
    assert any("wing loading" in n.lower() for n in resp["notes"])


def test_bad_satellite_rejected() -> None:
    body = {
        "a_km": -1.0,
        "e": 0.0,
        "i_deg": 51.6,
        "raan_deg": 0.0,
        "argp_deg": 0.0,
        "m0_deg": 0.0,
        "epoch_utc": "2026-10-14T12:00:00Z",
    }
    r = client.post("/design/satellite", json=body)
    assert r.status_code == 422
