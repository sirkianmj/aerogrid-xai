"""Sensitivity analysis of delivered power.

Verifies that the endpoint returns a ranked list of parameter
sensitivities, that the transmitter power elasticity is close to 1
(linear coupling through the cascade), and that the ranking is by
|elasticity|.
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def _base_body() -> dict[str, object]:
    return {
        "seed": 20261014,
        "satellite_key": "iss",
        "n_uavs": 6,
        "ground_lat_deg": 40.798,
        "ground_lon_deg": -77.86,
        "transmitter_power_w": 10000.0,
        "visibility_km": 10.0,
        "cloud_factor": 0.0,
        "transmitter_aperture_m": 0.02,
        "uav_alt_m": 1000.0,
        "uav_receiver_aperture_m2": 0.5,
        "uav_receiver_type": "laser_photovoltaic",
    }


def test_sensitivity_returns_a_report() -> None:
    r = client.post(
        "/discovery/sensitivity",
        json={"base": _base_body()},
    )
    assert r.status_code == 200
    body = r.json()
    assert "base_delivered_power_w" in body
    assert body["base_delivered_power_w"] > 0.0
    assert "parameters" in body
    assert len(body["parameters"]) >= 5


def test_transmitter_power_elasticity_near_one() -> None:
    """The cascade is linear in transmitter power through the beam
    stage, so a 1% change in power gives ~1% change in delivered
    power. The elasticity is 1.0 up to the small nonlinearity from the
    receiver's efficiency curve."""
    r = client.post(
        "/discovery/sensitivity",
        json={"base": _base_body()},
    )
    body = r.json()
    tx = next(p for p in body["parameters"] if p["name"] == "transmitter_power_w")
    assert tx["elasticity"] is not None
    # Within 5% of unity. The deviation is the receiver's power-
    # dependent efficiency.
    assert 0.90 <= tx["elasticity"] <= 1.10


def test_transmitter_aperture_increases_power() -> None:
    """A larger beam waist at the transmitter means less spreading at
    range, so more power captured by the receiver aperture. The
    elasticity is positive."""
    r = client.post(
        "/discovery/sensitivity",
        json={"base": _base_body()},
    )
    body = r.json()
    ap = next(p for p in body["parameters"] if p["name"] == "transmitter_aperture_m")
    assert ap["elasticity"] is not None
    assert ap["elasticity"] > 0.0


def test_receiver_aperture_increases_power() -> None:
    """A larger receiver area captures more of the beam. Positive
    elasticity, expected order of magnitude ~1 (linear in area in the
    spillover-limited regime)."""
    r = client.post(
        "/discovery/sensitivity",
        json={"base": _base_body()},
    )
    body = r.json()
    ap = next(p for p in body["parameters"] if p["name"] == "uav_receiver_aperture_m2")
    assert ap["elasticity"] is not None
    assert ap["elasticity"] > 0.0


def test_parameters_are_ranked_by_absolute_elasticity() -> None:
    r = client.post(
        "/discovery/sensitivity",
        json={"base": _base_body()},
    )
    body = r.json()
    elasticities = [abs(p["elasticity"]) for p in body["parameters"] if p["elasticity"] is not None]
    assert elasticities == sorted(elasticities, reverse=True)
