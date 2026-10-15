"""Signup flow tests.

The tests require a running PostgreSQL with the migrations applied
(001 through 006). They skip cleanly when the database is unreachable
so the pytest job does not fail on a machine without Postgres, and the
RLS-isolation CI job treats a skip as an error because the database is
always present there.
"""

from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.main import app
from app.saas.db import admin_session

client = TestClient(app)


def _db_reachable() -> bool:
    try:
        with admin_session() as s:
            s.execute(text("SELECT 1"))
        return True
    except Exception:
        return False


pytestmark = pytest.mark.skipif(
    not _db_reachable(),
    reason="PostgreSQL not reachable; signup tests require the database",
)


def _unique_slug() -> str:
    return f"test-{uuid.uuid4().hex[:12]}"


def _cleanup(slug: str) -> None:
    with admin_session() as s:
        s.execute(text("DELETE FROM tenants WHERE slug = :slug"), {"slug": slug})


def test_signup_creates_tenant_and_returns_token() -> None:
    slug = _unique_slug()
    try:
        r = client.post(
            "/auth/signup",
            json={
                "slug": slug,
                "display_name": "Test Tenant",
                "password": "correct-horse-battery-staple",
            },
        )
        assert r.status_code == 201, r.text
        body = r.json()
        assert body["token"]
        assert body["role"] == "admin"
        assert body["expires_in_seconds"] == 86_400
        # The tenant row must be readable by admin and have the display
        # name set.
        with admin_session() as s:
            row = s.execute(
                text("SELECT display_name FROM tenants WHERE slug = :slug"),
                {"slug": slug},
            ).first()
        assert row is not None
        assert row[0] == "Test Tenant"
    finally:
        _cleanup(slug)


def test_signup_then_signin_with_same_credentials() -> None:
    slug = _unique_slug()
    password = "correct-horse-battery-staple"
    try:
        r = client.post(
            "/auth/signup",
            json={
                "slug": slug,
                "display_name": "Test Tenant",
                "password": password,
            },
        )
        assert r.status_code == 201, r.text
        r2 = client.post("/auth/token", json={"slug": slug, "password": password})
        assert r2.status_code == 200, r2.text
        assert r2.json()["role"] == "admin"
    finally:
        _cleanup(slug)


def test_signup_rejects_duplicate_slug() -> None:
    slug = _unique_slug()
    try:
        r1 = client.post(
            "/auth/signup",
            json={
                "slug": slug,
                "display_name": "First",
                "password": "correct-horse-battery-staple",
            },
        )
        assert r1.status_code == 201, r1.text
        r2 = client.post(
            "/auth/signup",
            json={
                "slug": slug,
                "display_name": "Second",
                "password": "correct-horse-battery-staple",
            },
        )
        assert r2.status_code == 409
        assert slug in r2.json()["detail"]
    finally:
        _cleanup(slug)


def test_signup_rejects_short_password() -> None:
    r = client.post(
        "/auth/signup",
        json={"slug": _unique_slug(), "display_name": "T", "password": "short"},
    )
    assert r.status_code == 422


def test_signup_rejects_bad_slug_format() -> None:
    for bad in ["UPPER", "ab", "has space", "-leading-hyphen", "trailing-"]:
        r = client.post(
            "/auth/signup",
            json={
                "slug": bad,
                "display_name": "T",
                "password": "correct-horse-battery-staple",
            },
        )
        assert r.status_code == 422, f"slug {bad!r} should be rejected"


def test_signup_rejects_empty_display_name() -> None:
    r = client.post(
        "/auth/signup",
        json={
            "slug": _unique_slug(),
            "display_name": "",
            "password": "correct-horse-battery-staple",
        },
    )
    assert r.status_code == 422


def test_signup_does_not_require_existing_tenant() -> None:
    """A caller with no credentials at all can sign up."""
    slug = _unique_slug()
    try:
        r = client.post(
            "/auth/signup",
            json={
                "slug": slug,
                "display_name": "Anonymous",
                "password": "correct-horse-battery-staple",
            },
        )
        assert r.status_code == 201
    finally:
        _cleanup(slug)
