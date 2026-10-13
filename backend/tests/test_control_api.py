"""Tests for the Tier 1 decisions HTTP endpoint."""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def _candidate(
    uav_id: int,
    battery_pct: float,
    mission_priority: float = 0.5,
    network_centrality: float = 0.5,
    coverage_contribution: float = 0.1,
    workload_urgency: float = 0.5,
    thermal_headroom_c: float = 40.0,
    atmospheric_factor: float = 0.9,
    beam_alignment: float = 0.95,
    transfer_loss: float = 0.1,
) -> dict[str, float]:
    return {
        "uav_id": float(uav_id),
        "battery_pct": battery_pct,
        "mission_priority": mission_priority,
        "network_centrality": network_centrality,
        "coverage_contribution": coverage_contribution,
        "workload_urgency": workload_urgency,
        "thermal_headroom_c": thermal_headroom_c,
        "atmospheric_factor": atmospheric_factor,
        "beam_alignment": beam_alignment,
        "transfer_loss": transfer_loss,
    }


# -- Happy path -------------------------------------------------------------


def test_charge_endpoint_returns_trace() -> None:
    body = {
        "candidates": [
            _candidate(uav_id=32, battery_pct=19.0, mission_priority=0.9),
            _candidate(uav_id=18, battery_pct=55.0, mission_priority=0.4),
        ]
    }
    response = client.post("/decisions/charge", json=body)
    assert response.status_code == 200
    payload = response.json()

    assert payload["epistemic_tag"] == "tier1_decision_trace"
    assert payload["decision"].startswith("charge_uav_")
    assert payload["decision_kind"] == "charge"
    assert isinstance(payload["primary_reasons"], list)
    assert isinstance(payload["consulted_rules"], list)
    assert 0.0 <= payload["confidence"] <= 1.0
    assert (
        "physical-reality" in payload["confidence_note"].lower()
        or "physical reality" in payload["confidence_note"].lower()
    )


def test_charge_endpoint_selects_low_battery_high_priority() -> None:
    """The default rule list weights low battery and high priority.
    UAV 32 with 19% battery and priority 0.9 should beat UAV 18 with
    55% battery and priority 0.4, on the rule weights."""
    body = {
        "candidates": [
            _candidate(uav_id=32, battery_pct=19.0, mission_priority=0.9),
            _candidate(uav_id=18, battery_pct=55.0, mission_priority=0.4),
        ]
    }
    response = client.post("/decisions/charge", json=body)
    payload = response.json()
    assert payload["decision"] == "charge_uav_32"
    assert payload["alternative"]["action"] == "charge_uav_18"


def test_charge_endpoint_records_primary_reasons() -> None:
    body = {"candidates": [_candidate(uav_id=1, battery_pct=10.0, mission_priority=0.9)]}
    response = client.post("/decisions/charge", json=body)
    payload = response.json()
    assert len(payload["primary_reasons"]) > 0
    for reason in payload["primary_reasons"]:
        assert "label" in reason and "comparison" in reason and "weight" in reason


def test_charge_endpoint_records_consulted_rules() -> None:
    """Every rule is consulted, matched or not."""
    body = {"candidates": [_candidate(uav_id=1, battery_pct=50.0)]}
    response = client.post("/decisions/charge", json=body)
    payload = response.json()
    # The default rule list has 9 rules.
    assert len(payload["consulted_rules"]) >= 9


# -- Tier 2 estimates pass-through ------------------------------------------


def test_charge_endpoint_merges_estimates_into_inputs() -> None:
    """An estimate key reaches the rule predicate.

    The candidate mapping is merged over the estimates mapping, so a
    candidate that sets a key explicitly overrides the estimate for
    that key. This test omits ``atmospheric_factor`` from the candidate
    so the estimate takes effect. The default rule list fires
    ``atmosphere_favorable`` when ``atmospheric_factor >= 0.8``.
    """
    candidate = _candidate(uav_id=1, battery_pct=10.0)
    del candidate["atmospheric_factor"]
    body = {
        "candidates": [candidate],
        "estimates": {"atmospheric_factor": 0.95},
    }
    response = client.post("/decisions/charge", json=body)
    payload = response.json()
    matched_labels = [r["label"] for r in payload["primary_reasons"]]
    assert any("atmosphere_favorable" in label for label in matched_labels)


def test_charge_endpoint_candidate_overrides_estimate() -> None:
    """When the candidate sets a key explicitly, it wins over the estimate.

    This is the documented merge order of decide_charge_uav: the merged
    input is ``{**estimates, **candidate}``.
    """
    body = {
        "candidates": [_candidate(uav_id=1, battery_pct=10.0, atmospheric_factor=0.5)],
        "estimates": {"atmospheric_factor": 0.95},
    }
    response = client.post("/decisions/charge", json=body)
    payload = response.json()
    matched_labels = [r["label"] for r in payload["primary_reasons"]]
    assert not any("atmosphere_favorable" in label for label in matched_labels)


# -- Validation -------------------------------------------------------------


def test_charge_endpoint_rejects_empty_candidates() -> None:
    response = client.post("/decisions/charge", json={"candidates": []})
    assert response.status_code == 422


def test_charge_endpoint_rejects_candidate_without_uav_id() -> None:
    body = {"candidates": [{"battery_pct": 10.0}]}
    response = client.post("/decisions/charge", json=body)
    assert response.status_code == 400
    assert "uav_id" in response.json()["detail"]


def test_charge_endpoint_rejects_malformed_body() -> None:
    response = client.post("/decisions/charge", json={"bogus": 1})
    assert response.status_code == 422


# -- Health still works -----------------------------------------------------


def test_health_endpoint_still_works() -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "healthy"}


def test_openapi_lists_decisions_route() -> None:
    response = client.get("/openapi.json")
    assert response.status_code == 200
    paths = response.json()["paths"]
    assert "/decisions/charge" in paths
    assert "post" in paths["/decisions/charge"]
