"""Tests for the SaaS HTTP routes.

The mission-count route queries PostgreSQL through tenant_session, so
this module requires a running PostgreSQL with the RLS migration
applied. It skips cleanly if the database is not reachable, matching the
convention in test_rls_isolation.py.
"""

from __future__ import annotations

import uuid
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.main import app
from app.saas.auth import Role, issue_token
from app.saas.db import admin_session, get_engine, tenant_session

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
        "and apply backend/app/saas/migrations/001_rls_setup.sql"
    ),
)


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Clear any inherited AEROGRID_JWT_SECRET so tests use the dev default."""
    monkeypatch.delenv("AEROGRID_JWT_SECRET", raising=False)
    monkeypatch.delenv("AEROGRID_ENV", raising=False)


@pytest.fixture()
def tenant_with_missions() -> Iterator[uuid.UUID]:
    tid = uuid.uuid4()
    with admin_session() as s:
        s.execute(
            text("INSERT INTO tenants (id, slug, display_name) VALUES (:i, :s, :n)"),
            {"i": str(tid), "s": f"t-{tid.hex[:8]}", "n": "Test"},
        )
    with tenant_session(tid) as s:
        for name in ("m1", "m2"):
            s.execute(
                text("INSERT INTO missions (id, tenant_id, name) VALUES (:i, :t, :n)"),
                {"i": str(uuid.uuid4()), "t": str(tid), "n": name},
            )
    try:
        yield tid
    finally:
        with admin_session() as s:
            s.execute(text("DELETE FROM tenants WHERE id = :i"), {"i": str(tid)})


def _auth_header(tid: uuid.UUID, role: Role) -> dict[str, str]:
    return {"Authorization": f"Bearer {issue_token(tid, role)}"}


# -- /saas/whoami ----------------------------------------------------------


def test_whoami_401_without_token() -> None:
    r = client.get("/saas/whoami")
    assert r.status_code == 401


def test_whoami_200_with_token(tenant_with_missions: uuid.UUID) -> None:
    tid = tenant_with_missions
    r = client.get("/saas/whoami", headers=_auth_header(tid, Role.VIEWER))
    assert r.status_code == 200
    payload = r.json()
    assert payload["tenant_id"] == str(tid)
    assert payload["role"] == "viewer"
    assert payload["is_superadmin"] is False


def test_whoami_superadmin_flag(tenant_with_missions: uuid.UUID) -> None:
    tid = tenant_with_missions
    r = client.get("/saas/whoami", headers=_auth_header(tid, Role.SUPERADMIN))
    payload = r.json()
    assert payload["role"] == "superadmin"
    assert payload["is_superadmin"] is True


# -- /saas/mission-count ---------------------------------------------------


def test_mission_count_requires_token() -> None:
    r = client.get("/saas/mission-count")
    assert r.status_code == 401


def test_mission_count_is_tenant_scoped(tenant_with_missions: uuid.UUID) -> None:
    """The count comes from a tenant_session, so PostgreSQL RLS filters
    it. A caller with the right JWT for tenant A sees only A's missions.
    """
    tid = tenant_with_missions
    r = client.get("/saas/mission-count", headers=_auth_header(tid, Role.VIEWER))
    assert r.status_code == 200
    payload = r.json()
    assert payload["tenant_id"] == str(tid)
    assert payload["n_missions"] == 2


def test_mission_count_differs_for_a_tenant_with_no_missions() -> None:
    """A tenant that owns no missions sees zero, even though other
    tenants' missions exist in the table."""
    # Create tenant A with missions.
    a = uuid.uuid4()
    with admin_session() as s:
        s.execute(
            text("INSERT INTO tenants (id, slug, display_name) VALUES (:i, :s, :n)"),
            {"i": str(a), "s": f"a-{a.hex[:6]}", "n": "A"},
        )
    with tenant_session(a) as s:
        s.execute(
            text("INSERT INTO missions (id, tenant_id, name) VALUES (:i, :t, :n)"),
            {"i": str(uuid.uuid4()), "t": str(a), "n": "a-only"},
        )
    # Create tenant B with no missions.
    b = uuid.uuid4()
    with admin_session() as s:
        s.execute(
            text("INSERT INTO tenants (id, slug, display_name) VALUES (:i, :s, :n)"),
            {"i": str(b), "s": f"b-{b.hex[:6]}", "n": "B"},
        )
    try:
        r = client.get("/saas/mission-count", headers=_auth_header(b, Role.VIEWER))
        assert r.status_code == 200
        assert r.json()["n_missions"] == 0
    finally:
        with admin_session() as s:
            s.execute(text("DELETE FROM tenants WHERE id IN (:a, :b)"), {"a": str(a), "b": str(b)})
