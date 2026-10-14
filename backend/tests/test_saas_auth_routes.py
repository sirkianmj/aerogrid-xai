"""Tests for POST /auth/token (real sign-in flow).

The endpoint exchanges tenant slug + password for a JWT. Passwords are
bcrypt hashes stored via pgcrypto; verification happens inside
PostgreSQL. These tests exercise the four properties the endpoint must
have: correct credentials authenticate; wrong credentials are refused
uniformly; the issued token is accepted by a protected endpoint; and
a tenant without a password cannot log in at all.

The whole module skips if PostgreSQL is not reachable, matching the
convention of the other DB-backed test modules. In the rls-isolation
CI job (which has a service container) it runs.
"""

from __future__ import annotations

import uuid
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.main import app
from app.saas.db import admin_session, get_engine

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
def tenant_with_password() -> Iterator[tuple[str, str]]:
    """Provision a tenant with a known password. Yields (slug, password)."""
    slug = f"login-{uuid.uuid4().hex[:8]}"
    password = "correct-horse-battery-staple"
    with admin_session() as s:
        s.execute(
            text(
                "INSERT INTO tenants (slug, display_name, password_hash) "
                "VALUES (:s, :n, crypt(:p, gen_salt('bf', 12)))"
            ),
            {"s": slug, "n": "Login Test", "p": password},
        )
    try:
        yield (slug, password)
    finally:
        with admin_session() as s:
            s.execute(text("DELETE FROM tenants WHERE slug = :s"), {"s": slug})


@pytest.fixture()
def tenant_without_password() -> Iterator[str]:
    """Provision a tenant whose password_hash is NULL."""
    slug = f"nopass-{uuid.uuid4().hex[:8]}"
    with admin_session() as s:
        s.execute(
            text("INSERT INTO tenants (slug, display_name) VALUES (:s, :n)"),
            {"s": slug, "n": "No Password"},
        )
    try:
        yield slug
    finally:
        with admin_session() as s:
            s.execute(text("DELETE FROM tenants WHERE slug = :s"), {"s": slug})


# --- happy path ----------------------------------------------------------


def test_login_returns_token_for_correct_credentials(
    tenant_with_password: tuple[str, str],
) -> None:
    slug, password = tenant_with_password
    r = client.post("/auth/token", json={"slug": slug, "password": password})
    assert r.status_code == 200
    body = r.json()
    assert isinstance(body["token"], str) and body["token"].count(".") == 2
    assert body["role"] == "admin"
    assert body["expires_in_seconds"] == 86_400
    uuid.UUID(body["tenant_id"])  # valid UUID


def test_issued_token_is_accepted_by_protected_endpoint(
    tenant_with_password: tuple[str, str],
) -> None:
    slug, password = tenant_with_password
    tok = client.post("/auth/token", json={"slug": slug, "password": password}).json()["token"]
    r = client.get("/saas/whoami", headers={"Authorization": f"Bearer {tok}"})
    assert r.status_code == 200
    body = r.json()
    assert body["role"] == "admin"
    assert body["is_superadmin"] is False


def test_issued_token_is_scoped_to_the_tenant(
    tenant_with_password: tuple[str, str],
) -> None:
    """The token's sub claim is the tenant that logged in, and /saas/whoami
    echoes it back. This is the property that keeps tenant-scoped RLS
    queries confined to the caller's tenant."""
    slug, password = tenant_with_password
    issued = client.post("/auth/token", json={"slug": slug, "password": password}).json()
    r = client.get(
        "/saas/whoami",
        headers={"Authorization": f"Bearer {issued['token']}"},
    ).json()
    assert r["tenant_id"] == issued["tenant_id"]


# --- failure modes — all must be uniform 401 -----------------------------


def test_login_rejects_wrong_password(
    tenant_with_password: tuple[str, str],
) -> None:
    slug, _ = tenant_with_password
    r = client.post("/auth/token", json={"slug": slug, "password": "wrong"})
    assert r.status_code == 401
    assert r.json()["detail"] == "invalid credentials"


def test_login_rejects_unknown_slug() -> None:
    r = client.post(
        "/auth/token",
        json={"slug": "this-slug-does-not-exist-anywhere", "password": "x"},
    )
    assert r.status_code == 401
    assert r.json()["detail"] == "invalid credentials"


def test_login_rejects_tenant_without_password(tenant_without_password: str) -> None:
    slug = tenant_without_password
    r = client.post("/auth/token", json={"slug": slug, "password": "anything"})
    assert r.status_code == 401
    assert r.json()["detail"] == "invalid credentials"


def test_wrong_password_and_unknown_slug_return_the_same_detail(
    tenant_with_password: tuple[str, str],
) -> None:
    """Information-leak prevention: the endpoint must not distinguish
    'no such tenant' from 'wrong password'. Both produce the same
    status and the same detail string."""
    slug, _ = tenant_with_password
    r_wrong = client.post("/auth/token", json={"slug": slug, "password": "wrong"})
    r_unknown = client.post(
        "/auth/token", json={"slug": "definitely-not-a-real-slug", "password": "x"}
    )
    assert r_wrong.status_code == r_unknown.status_code == 401
    assert r_wrong.json()["detail"] == r_unknown.json()["detail"]


# --- request validation -------------------------------------------------


def test_login_rejects_empty_slug() -> None:
    r = client.post("/auth/token", json={"slug": "", "password": "x"})
    assert r.status_code == 422


def test_login_rejects_empty_password(
    tenant_with_password: tuple[str, str],
) -> None:
    slug, _ = tenant_with_password
    r = client.post("/auth/token", json={"slug": slug, "password": ""})
    assert r.status_code == 422


def test_login_rejects_missing_fields() -> None:
    r = client.post("/auth/token", json={})
    assert r.status_code == 422
    r = client.post("/auth/token", json={"slug": "x"})
    assert r.status_code == 422
