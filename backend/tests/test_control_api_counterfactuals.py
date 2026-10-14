"""The API exposes rule-ablation counterfactuals on /decisions/charge.

Section 26: for every rule that fires on the winner of the decision,
the API returns a counterfactual showing whether removing that rule
would have changed the outcome. This is the design-suggestion surface:
a `changed: true` entry names exactly which constraint is binding.
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)

# A candidate set designed so that at least one rule fires: the low
# battery candidate and the high priority candidate will each be
# favoured by distinct rules, and neither dominates on every metric.
_CANDIDATES = [
    {
        "uav_id": 1.0,
        "battery_pct": 10.0,
        "mission_priority": 0.9,
        "network_centrality": 0.7,
        "coverage_contribution": 0.08,
        "workload_urgency": 0.8,
        "thermal_headroom_c": 40.0,
        "atmospheric_factor": 0.9,
        "beam_alignment": 0.92,
        "transfer_loss": 0.12,
    },
    {
        "uav_id": 2.0,
        "battery_pct": 55.0,
        "mission_priority": 0.4,
        "network_centrality": 0.5,
        "coverage_contribution": 0.03,
        "workload_urgency": 0.4,
        "thermal_headroom_c": 45.0,
        "atmospheric_factor": 0.88,
        "beam_alignment": 0.90,
        "transfer_loss": 0.14,
    },
]


def test_counterfactuals_field_present() -> None:
    r = client.post("/decisions/charge", json={"candidates": _CANDIDATES})
    assert r.status_code == 200
    body = r.json()
    assert "counterfactuals" in body
    assert isinstance(body["counterfactuals"], list)


def test_one_counterfactual_per_fired_rule() -> None:
    """The number of counterfactuals equals the number of matched rules."""
    r = client.post("/decisions/charge", json={"candidates": _CANDIDATES})
    body = r.json()
    n_fired = len(body["primary_reasons"])
    assert len(body["counterfactuals"]) == n_fired


def test_counterfactual_shape_and_consistency() -> None:
    """Every counterfactual has the fields, and `changed` matches the strings."""
    r = client.post("/decisions/charge", json={"candidates": _CANDIDATES})
    body = r.json()
    for cf in body["counterfactuals"]:
        assert isinstance(cf["removed_rule"], str) and cf["removed_rule"]
        assert cf["original_selected"] == body["decision"]
        assert isinstance(cf["would_select"], str) and cf["would_select"]
        assert isinstance(cf["changed"], bool)
        assert cf["changed"] == (cf["would_select"] != cf["original_selected"])
        assert isinstance(cf["original_winner_score"], (int, float))
        assert isinstance(cf["ablated_winner_score"], (int, float))


def test_empty_when_no_rule_fires() -> None:
    """A degenerate candidate set with only one entry: no alternative exists,
    so no rule can change the winner; the list should be empty or all-changed=false."""
    r = client.post(
        "/decisions/charge",
        json={"candidates": [{"uav_id": 0.0, "battery_pct": 50.0}]},
    )
    assert r.status_code == 200
    body = r.json()
    # With a single candidate, ablating any rule cannot flip the decision.
    for cf in body["counterfactuals"]:
        assert cf["changed"] is False
