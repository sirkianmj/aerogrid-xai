"""Tests for the SaaS admin routes.

Both admin endpoints require the superadmin role and use admin_session
(superuser, cross-tenant by design). The tests provision tenants
directly via admin_session and exercise the two endpoints under every
role: no token (401), viewer (403), admin (403), superadmin (200).

The whole module skips if PostgreSQL is not reachable, matching the
convention in test_rls_isolation.py and test_saas_routes.py.
"""

from __future__ import annotations

import uuid
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.main import app
from app.saas.auth import Role, issue_token
from app.saas.db import admin_session, get_engine
from app.saas.quota import Metric, current_period_start

client = TestClient(app)


def _postgres_reachable() -> bool:
    try:
        with get_engine().connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False


pytestmark = pytest.mark.skipif(
    not _postgres_reachable(),
    reason=(
        "PostgreSQL is not reachable; start it with scripts/start_services.sh "
        "and apply backend/app/saas/migrations/*.sql"
    ),
)


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("AEROGRID_JWT_SECRET", raising=False)
    monkeypatch.delenv("AEROGRID_ENV", raising=False)


@pytest.fixture()
def two_tenants() -> Iterator[tuple[uuid.UUID, uuid.UUID]]:
    a = uuid.uuid4()
    b = uuid.uuid4()
    with admin_session() as s:
        s.execute(
            text("INSERT INTO tenants (id, slug, display_name) VALUES (:i, :s, :n)"),
            {"i": str(a), "s": f"adm-a-{a.hex[:8]}", "n": "Admin A"},
        )
        s.execute(
            text("INSERT INTO tenants (id, slug, display_name) VALUES (:i, :s, :n)"),
            {"i": str(b), "s": f"adm-b-{b.hex[:8]}", "n": "Admin B"},
        )
    try:
        yield (a, b)
    finally:
        with admin_session() as s:
            s.execute(
                text("DELETE FROM tenants WHERE id IN (:a, :b)"),
                {"a": str(a), "b": str(b)},
            )


def _auth(tid: uuid.UUID, role: Role) -> dict[str, str]:
    return {"Authorization": f"Bearer {issue_token(tid, role)}"}


# --- GET /saas/admin/tenants ----------------------------------------------


def test_list_tenants_requires_token() -> None:
    r = client.get("/saas/admin/tenants")
    assert r.status_code == 401


def test_list_tenants_rejects_viewer(two_tenants: tuple[uuid.UUID, uuid.UUID]) -> None:
    a, _ = two_tenants
    r = client.get("/saas/admin/tenants", headers=_auth(a, Role.VIEWER))
    assert r.status_code == 403


def test_list_tenants_rejects_admin(two_tenants: tuple[uuid.UUID, uuid.UUID]) -> None:
    a, _ = two_tenants
    r = client.get("/saas/admin/tenants", headers=_auth(a, Role.ADMIN))
    assert r.status_code == 403


def test_list_tenants_allows_superadmin(
    two_tenants: tuple[uuid.UUID, uuid.UUID],
) -> None:
    a, b = two_tenants
    r = client.get("/saas/admin/tenants", headers=_auth(a, Role.SUPERADMIN))
    assert r.status_code == 200
    body = r.json()
    assert body["count"] >= 2
    ids = {row["id"] for row in body["tenants"]}
    assert str(a) in ids
    assert str(b) in ids
    for row in body["tenants"]:
        assert row["plan"] in ("free", "pro", "enterprise")
        assert "created_at" in row
        assert "slug" in row


# --- GET /saas/admin/tenants/{tenant_id}/usage ----------------------------


def test_usage_requires_token(two_tenants: tuple[uuid.UUID, uuid.UUID]) -> None:
    a, _ = two_tenants
    r = client.get(f"/saas/admin/tenants/{a}/usage")
    assert r.status_code == 401


def test_usage_rejects_admin(two_tenants: tuple[uuid.UUID, uuid.UUID]) -> None:
    a, _ = two_tenants
    r = client.get(f"/saas/admin/tenants/{a}/usage", headers=_auth(a, Role.ADMIN))
    assert r.status_code == 403


def test_usage_returns_all_metrics_with_zero_defaults(
    two_tenants: tuple[uuid.UUID, uuid.UUID],
) -> None:
    a, _ = two_tenants
    r = client.get(f"/saas/admin/tenants/{a}/usage", headers=_auth(a, Role.SUPERADMIN))
    assert r.status_code == 200
    body = r.json()
    assert body["tenant_id"] == str(a)
    assert body["plan"] == "free"
    assert body["period_start"] == current_period_start().isoformat()
    metric_names = {m["metric"] for m in body["usage"]}
    assert metric_names == {m.value for m in Metric}
    for m in body["usage"]:
        assert m["count"] == 0
        assert m["limit"] > 0


def test_usage_reflects_recorded_counters(
    two_tenants: tuple[uuid.UUID, uuid.UUID],
) -> None:
    a, _ = two_tenants
    period = current_period_start()
    with admin_session() as s:
        s.execute(
            text(
                "INSERT INTO quota_usage (tenant_id, metric, period_start, count) "
                "VALUES (:t, :m, :p, :c)"
            ),
            {
                "t": str(a),
                "m": Metric.TRADESPACE_RUNS.value,
                "p": period,
                "c": 7,
            },
        )
    r = client.get(f"/saas/admin/tenants/{a}/usage", headers=_auth(a, Role.SUPERADMIN))
    assert r.status_code == 200
    body = r.json()
    by_metric = {m["metric"]: m["count"] for m in body["usage"]}
    assert by_metric["tradespace_runs"] == 7
    assert by_metric["z3_solves"] == 0
    assert by_metric["clear_d_runs"] == 0


def test_usage_404_for_unknown_tenant(two_tenants: tuple[uuid.UUID, uuid.UUID]) -> None:
    a, _ = two_tenants
    unknown = uuid.uuid4()
    r = client.get(f"/saas/admin/tenants/{unknown}/usage", headers=_auth(a, Role.SUPERADMIN))
    assert r.status_code == 404
