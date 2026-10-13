"""Tests for the Trade Space HTTP endpoint."""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_run_default_body_returns_pareto_front() -> None:
    response = client.post("/tradespace/run", json={})
    assert response.status_code == 200
    payload = response.json()
    assert payload["epistemic_tag"] == "simulation_result"
    assert payload["objective_labels"] == ["C", "R", "E", "N", "T", "U"]
    assert payload["negative_objectives"] == [5]
    assert payload["n_pareto"] >= 1
    assert len(payload["pareto_front"]) == payload["n_pareto"]


def test_run_pareto_points_have_six_objectives() -> None:
    response = client.post("/tradespace/run", json={"population_size": 12, "n_generations": 3})
    payload = response.json()
    for point in payload["pareto_front"]:
        assert len(point["objectives"]) == 6
        assert point["node_count"] >= 2
        assert point["link_count"] >= 1


def test_run_hypervolume_history_has_one_entry_per_generation() -> None:
    n_gen = 4
    response = client.post(
        "/tradespace/run",
        json={"population_size": 10, "n_generations": n_gen},
    )
    payload = response.json()
    assert len(payload["hypervolume_history"]) == n_gen
    for v in payload["hypervolume_history"]:
        assert v >= 0.0


def test_run_is_deterministic_for_a_fixed_seed() -> None:
    body = {"population_size": 10, "n_generations": 3, "seed": 1234}
    a = client.post("/tradespace/run", json=body).json()
    b = client.post("/tradespace/run", json=body).json()
    assert a["pareto_front"] == b["pareto_front"]
    assert a["hypervolume_history"] == b["hypervolume_history"]


def test_run_rejects_population_below_two() -> None:
    response = client.post("/tradespace/run", json={"population_size": 1})
    assert response.status_code == 422


def test_run_rejects_population_above_cap() -> None:
    response = client.post("/tradespace/run", json={"population_size": 10_000})
    assert response.status_code == 422


def test_run_rejects_generations_above_cap() -> None:
    response = client.post("/tradespace/run", json={"n_generations": 10_000})
    assert response.status_code == 422


def test_run_rejects_inconsistent_node_bounds() -> None:
    response = client.post(
        "/tradespace/run",
        json={"min_nodes": 10, "max_nodes": 5},
    )
    assert response.status_code == 400
    assert "max_nodes" in response.json()["detail"]


def test_run_rejects_hypervolume_samples_below_floor() -> None:
    response = client.post("/tradespace/run", json={"hypervolume_samples": 8})
    assert response.status_code == 422


def test_openapi_lists_all_routers() -> None:
    response = client.get("/openapi.json")
    paths = response.json()["paths"]
    assert "/decisions/charge" in paths
    assert "/orbital/satellites" in paths
    assert "/digital-twin/state" in paths
    assert "/tradespace/run" in paths
