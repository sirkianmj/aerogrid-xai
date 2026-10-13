"""Tests for the Trade Space HTTP endpoint.

The handler is authenticated (bearer JWT) and metered (per-tenant quota).
The DB-free tests provision a fake quota store and override the plan
dependency, so they continue to run in the backend CI job without a
database. Additional tests exercise the authentication and quota paths.
"""

from __future__ import annotations

import uuid
from collections.abc import Iterator

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.main import app as fastapi_app
from app.saas.auth import Role, issue_token
from app.saas.quota import (
    PLAN_LIMITS,
    FakeQuotaStore,
    Metric,
    Plan,
    current_period_start,
    get_tenant_plan,
)

TEST_TENANT_ID = uuid.UUID("11111111-1111-1111-1111-111111111111")


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("AEROGRID_JWT_SECRET", raising=False)
    monkeypatch.delenv("AEROGRID_ENV", raising=False)


@pytest.fixture()
def quota_store() -> FakeQuotaStore:
    return FakeQuotaStore()


@pytest.fixture()
def tradespace_app(quota_store: FakeQuotaStore) -> Iterator[FastAPI]:
    """Install a fake quota store on app.state and override the plan dep.

    The handler resolves the quota store from app.state (same convention
    as get_stripe_client and get_idempotency_store) and the plan from
    get_tenant_plan. Both are overridden so the tests do not touch
    PostgreSQL.
    """
    fastapi_app.state.quota_store = quota_store
    fastapi_app.dependency_overrides[get_tenant_plan] = lambda: Plan.PRO
    try:
        yield fastapi_app
    finally:
        fastapi_app.dependency_overrides.pop(get_tenant_plan, None)
        if hasattr(fastapi_app.state, "quota_store"):
            delattr(fastapi_app.state, "quota_store")


@pytest.fixture()
def client(tradespace_app: FastAPI) -> TestClient:
    return TestClient(tradespace_app)


@pytest.fixture()
def auth_headers() -> dict[str, str]:
    return {"Authorization": f"Bearer {issue_token(TEST_TENANT_ID, Role.ADMIN)}"}


def _usage(store: FakeQuotaStore) -> int:
    return store.peek(TEST_TENANT_ID, Metric.TRADESPACE_RUNS, current_period_start())


# --- existing coverage, with auth added -----------------------------------


def test_run_default_body_returns_pareto_front(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    response = client.post("/tradespace/run", json={}, headers=auth_headers)
    assert response.status_code == 200
    payload = response.json()
    assert payload["epistemic_tag"] == "simulation_result"
    assert payload["objective_labels"] == ["C", "R", "E", "N", "T", "U"]
    assert payload["negative_objectives"] == [5]
    assert payload["n_pareto"] >= 1
    assert len(payload["pareto_front"]) == payload["n_pareto"]


def test_run_pareto_points_have_six_objectives(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    response = client.post(
        "/tradespace/run",
        json={"population_size": 12, "n_generations": 3},
        headers=auth_headers,
    )
    payload = response.json()
    for point in payload["pareto_front"]:
        assert len(point["objectives"]) == 6
        assert point["node_count"] >= 2
        assert point["link_count"] >= 1


def test_run_hypervolume_history_has_one_entry_per_generation(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    n_gen = 4
    response = client.post(
        "/tradespace/run",
        json={"population_size": 10, "n_generations": n_gen},
        headers=auth_headers,
    )
    payload = response.json()
    assert len(payload["hypervolume_history"]) == n_gen
    for v in payload["hypervolume_history"]:
        assert v >= 0.0


def test_run_is_deterministic_for_a_fixed_seed(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    body = {"population_size": 10, "n_generations": 3, "seed": 1234}
    a = client.post("/tradespace/run", json=body, headers=auth_headers).json()
    b = client.post("/tradespace/run", json=body, headers=auth_headers).json()
    assert a["pareto_front"] == b["pareto_front"]
    assert a["hypervolume_history"] == b["hypervolume_history"]


def test_run_rejects_population_below_two(client: TestClient, auth_headers: dict[str, str]) -> None:
    response = client.post("/tradespace/run", json={"population_size": 1}, headers=auth_headers)
    assert response.status_code == 422


def test_run_rejects_population_above_cap(client: TestClient, auth_headers: dict[str, str]) -> None:
    response = client.post(
        "/tradespace/run", json={"population_size": 10_000}, headers=auth_headers
    )
    assert response.status_code == 422


def test_run_rejects_generations_above_cap(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    response = client.post("/tradespace/run", json={"n_generations": 10_000}, headers=auth_headers)
    assert response.status_code == 422


def test_run_rejects_inconsistent_node_bounds(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    response = client.post(
        "/tradespace/run",
        json={"min_nodes": 10, "max_nodes": 5},
        headers=auth_headers,
    )
    assert response.status_code == 400
    assert "max_nodes" in response.json()["detail"]


def test_run_rejects_hypervolume_samples_below_floor(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    response = client.post("/tradespace/run", json={"hypervolume_samples": 8}, headers=auth_headers)
    assert response.status_code == 422


def test_openapi_lists_all_routers() -> None:
    response = TestClient(fastapi_app).get("/openapi.json")
    paths = response.json()["paths"]
    assert "/decisions/charge" in paths
    assert "/orbital/satellites" in paths
    assert "/digital-twin/state" in paths
    assert "/tradespace/run" in paths


# --- new coverage: authentication -----------------------------------------


def test_run_without_auth_returns_401(client: TestClient, quota_store: FakeQuotaStore) -> None:
    response = client.post("/tradespace/run", json={})
    assert response.status_code == 401
    assert _usage(quota_store) == 0


def test_run_with_malformed_auth_returns_401(client: TestClient) -> None:
    response = client.post(
        "/tradespace/run",
        json={},
        headers={"Authorization": "Bearer not-a-jwt"},
    )
    assert response.status_code == 401


# --- new coverage: quota --------------------------------------------------


def test_run_returns_429_when_free_limit_exhausted(
    tradespace_app: FastAPI, quota_store: FakeQuotaStore
) -> None:
    tradespace_app.dependency_overrides[get_tenant_plan] = lambda: Plan.FREE
    client = TestClient(tradespace_app)
    headers = {"Authorization": f"Bearer {issue_token(TEST_TENANT_ID, Role.ADMIN)}"}
    limit = PLAN_LIMITS[Plan.FREE][Metric.TRADESPACE_RUNS]
    body = {"population_size": 4, "n_generations": 1}

    for i in range(limit):
        r = client.post("/tradespace/run", json=body, headers=headers)
        assert r.status_code == 200, f"call {i + 1}: {r.status_code} {r.text}"

    over = client.post("/tradespace/run", json=body, headers=headers)
    assert over.status_code == 429
    assert "Retry-After" in over.headers
    assert int(over.headers["Retry-After"]) >= 1


def test_run_does_not_charge_on_body_validation_error(
    client: TestClient, auth_headers: dict[str, str], quota_store: FakeQuotaStore
) -> None:
    response = client.post("/tradespace/run", json={"population_size": 1}, headers=auth_headers)
    assert response.status_code == 422
    assert _usage(quota_store) == 0


def test_run_does_not_charge_on_inconsistent_bounds(
    client: TestClient, auth_headers: dict[str, str], quota_store: FakeQuotaStore
) -> None:
    response = client.post(
        "/tradespace/run",
        json={"min_nodes": 10, "max_nodes": 5},
        headers=auth_headers,
    )
    assert response.status_code == 400
    assert _usage(quota_store) == 0


def test_run_charges_one_unit_per_successful_call(
    client: TestClient, auth_headers: dict[str, str], quota_store: FakeQuotaStore
) -> None:
    body = {"population_size": 4, "n_generations": 1}
    for expected in (1, 2, 3):
        r = client.post("/tradespace/run", json=body, headers=auth_headers)
        assert r.status_code == 200
        assert _usage(quota_store) == expected
