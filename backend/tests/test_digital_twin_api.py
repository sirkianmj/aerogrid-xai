"""Tests for the Digital Twin HTTP endpoints."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


# -- /digital-twin/state ---------------------------------------------------


def test_state_returns_steady_state_at_nominal_conditions() -> None:
    body = {
        "incident_power_w": 20.0,
        "airflow_m_per_s": 5.0,
        "ambient_temperature_k": 298.15,
    }
    response = client.post("/digital-twin/state", json=body)
    assert response.status_code == 200
    payload = response.json()

    assert payload["epistemic_tag"] == "simulation_result"
    assert payload["steady_state"] is not None
    ss = payload["steady_state"]
    # The Han et al. degradation regime: 20 W on 100 cm^2 with 5 m/s
    # airflow lands in the 80-90 C band for the PLC.
    assert 340.0 < ss["t_plc_k"] < 375.0
    assert ss["t_plc_c"] == ss["t_plc_k"] - 273.15
    assert ss["t_te_c"] == ss["t_te_k"] - 273.15


def test_state_reports_thermal_runaway_and_positive_margin() -> None:
    body = {
        "incident_power_w": 20.0,
        "airflow_m_per_s": 5.0,
        "ambient_temperature_k": 298.15,
    }
    payload = client.post("/digital-twin/state", json=body).json()
    assert payload["thermal_runaway_power_w"] > 20.0
    assert payload["safety_margin_w"] > 0.0
    assert 0.0 < payload["safety_margin_fraction"] < 1.0


def test_state_reports_receiver_efficiency_when_steady_state_exists() -> None:
    body = {
        "incident_power_w": 20.0,
        "airflow_m_per_s": 5.0,
        "ambient_temperature_k": 298.15,
    }
    payload = client.post("/digital-twin/state", json=body).json()
    assert payload["receiver_efficiency"] is not None
    assert 0.0 < payload["receiver_efficiency"] < 1.0
    assert "eta_total" in payload["receiver_efficiency_source"]


def test_state_rejects_negative_power() -> None:
    body = {
        "incident_power_w": -1.0,
        "airflow_m_per_s": 5.0,
        "ambient_temperature_k": 298.15,
    }
    response = client.post("/digital-twin/state", json=body)
    assert response.status_code == 422


def test_state_rejects_zero_ambient_temperature() -> None:
    body = {
        "incident_power_w": 20.0,
        "airflow_m_per_s": 5.0,
        "ambient_temperature_k": 0.0,
    }
    response = client.post("/digital-twin/state", json=body)
    assert response.status_code == 422


# -- /digital-twin/trajectory ----------------------------------------------


def test_trajectory_returns_requested_samples() -> None:
    body = {
        "incident_power_w": 20.0,
        "airflow_m_per_s": 5.0,
        "ambient_temperature_k": 298.15,
        "t_end_s": 600.0,
        "n_samples": 50,
    }
    response = client.post("/digital-twin/trajectory", json=body)
    assert response.status_code == 200
    payload = response.json()
    assert payload["epistemic_tag"] == "simulation_result"
    assert payload["n_samples"] == 50
    assert len(payload["samples"]) == 50


def test_trajectory_starts_at_ambient_and_rises() -> None:
    body = {
        "incident_power_w": 20.0,
        "airflow_m_per_s": 5.0,
        "ambient_temperature_k": 298.15,
        "t_end_s": 600.0,
        "n_samples": 100,
    }
    payload = client.post("/digital-twin/trajectory", json=body).json()
    samples = payload["samples"]
    assert samples[0]["t_plc_k"] == 298.15
    assert samples[0]["t_te_k"] == 298.15
    assert samples[-1]["t_plc_k"] > samples[0]["t_plc_k"]
    # The PLC is warmer than the TE in a heated stack.
    assert samples[-1]["t_plc_k"] > samples[-1]["t_te_k"]


def test_trajectory_rejects_over_cap_sample_count() -> None:
    body = {
        "incident_power_w": 20.0,
        "airflow_m_per_s": 5.0,
        "ambient_temperature_k": 298.15,
        "t_end_s": 600.0,
        "n_samples": 10_000,
    }
    response = client.post("/digital-twin/trajectory", json=body)
    assert response.status_code == 422


def test_trajectory_rejects_zero_horizon() -> None:
    body = {
        "incident_power_w": 20.0,
        "airflow_m_per_s": 5.0,
        "ambient_temperature_k": 298.15,
        "t_end_s": 0.0,
        "n_samples": 50,
    }
    response = client.post("/digital-twin/trajectory", json=body)
    assert response.status_code == 422


# -- /digital-twin/discrepancy ---------------------------------------------


def test_discrepancy_records_all_observations() -> None:
    body = {
        "observations": [
            {"field_name": "temperature_k", "predicted": 320.0, "observed": 321.0},
            {"field_name": "efficiency", "predicted": 0.20, "observed": 0.202},
            {"field_name": "received_power_w", "predicted": 100.0, "observed": 105.0},
        ]
    }
    response = client.post("/digital-twin/discrepancy", json=body)
    assert response.status_code == 200
    payload = response.json()
    assert payload["epistemic_tag"] == "simulation_result"
    assert payload["n_observations"] == 3
    assert len(payload["records"]) == 3


def test_discrepancy_flags_a_triggered_absolute_threshold() -> None:
    """temperature_k has an absolute threshold of 2.0 K; an error of 5 K
    exceeds it."""
    body = {
        "observations": [
            {"field_name": "temperature_k", "predicted": 320.0, "observed": 325.0},
        ]
    }
    payload = client.post("/digital-twin/discrepancy", json=body).json()
    assert payload["n_triggered"] == 1
    assert payload["should_refine"] is True
    assert "temperature_k" in payload["triggered_fields"]
    rec = payload["records"][0]
    assert rec["absolute_error"] == 5.0
    assert rec["triggered"] is True


def test_discrepancy_does_not_trigger_below_threshold() -> None:
    body = {
        "observations": [
            {"field_name": "temperature_k", "predicted": 320.0, "observed": 321.0},
        ]
    }
    payload = client.post("/digital-twin/discrepancy", json=body).json()
    assert payload["n_triggered"] == 0
    assert payload["should_refine"] is False


def test_discrepancy_flags_a_triggered_relative_threshold() -> None:
    """efficiency has a relative threshold of 0.05; 0.20 to 0.22 is 10
    percent, which exceeds it."""
    body = {
        "observations": [
            {"field_name": "efficiency", "predicted": 0.20, "observed": 0.22},
        ]
    }
    payload = client.post("/digital-twin/discrepancy", json=body).json()
    assert payload["n_triggered"] == 1
    assert payload["records"][0]["relative_error"] == pytest.approx(0.1)


def test_discrepancy_rejects_unknown_field() -> None:
    body = {
        "observations": [
            {"field_name": "not_a_real_field", "predicted": 1.0, "observed": 2.0},
        ]
    }
    response = client.post("/digital-twin/discrepancy", json=body)
    assert response.status_code == 400
    assert "not_a_real_field" in response.json()["detail"]


def test_discrepancy_rejects_empty_observations() -> None:
    response = client.post("/digital-twin/discrepancy", json={"observations": []})
    assert response.status_code == 422


def test_discrepancy_includes_threshold_summary() -> None:
    body = {
        "observations": [
            {"field_name": "temperature_k", "predicted": 320.0, "observed": 321.0},
        ]
    }
    payload = client.post("/digital-twin/discrepancy", json=body).json()
    summary = payload["threshold_summary"]
    assert "temperature_k" in summary
    assert summary["temperature_k"]["absolute"] == 2.0
    assert summary["efficiency"]["relative"] == 0.05


# -- Integration -----------------------------------------------------------


def test_health_still_works() -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "healthy"}


def test_openapi_lists_all_routers() -> None:
    response = client.get("/openapi.json")
    paths = response.json()["paths"]
    assert "/decisions/charge" in paths
    assert "/orbital/satellites" in paths
    assert "/digital-twin/state" in paths
    assert "/digital-twin/trajectory" in paths
    assert "/digital-twin/discrepancy" in paths
