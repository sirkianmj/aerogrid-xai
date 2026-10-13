"""Tests for tenant JWT authentication."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import jwt
import pytest
from fastapi import HTTPException
from starlette.datastructures import Headers
from starlette.requests import Request

from app.saas.auth import (
    ALGORITHM,
    DEV_SECRET,
    Role,
    TenantContext,
    decode_token,
    issue_token,
    require_role,
    require_tenant,
    signing_secret,
)

# -- signing_secret --------------------------------------------------------


def test_signing_secret_defaults_in_development(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("AEROGRID_ENV", raising=False)
    monkeypatch.delenv("AEROGRID_JWT_SECRET", raising=False)
    assert signing_secret() == DEV_SECRET


def test_signing_secret_env_override_in_development(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AEROGRID_ENV", "development")
    monkeypatch.setenv("AEROGRID_JWT_SECRET", "custom-dev")
    assert signing_secret() == "custom-dev"


def test_signing_secret_requires_env_var_in_production(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AEROGRID_ENV", "production")
    monkeypatch.delenv("AEROGRID_JWT_SECRET", raising=False)
    with pytest.raises(RuntimeError, match="AEROGRID_JWT_SECRET must be set"):
        signing_secret()


def test_signing_secret_rejects_dev_default_in_production(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("AEROGRID_ENV", "production")
    monkeypatch.setenv("AEROGRID_JWT_SECRET", DEV_SECRET)
    with pytest.raises(RuntimeError, match="development default"):
        signing_secret()


def test_signing_secret_accepts_real_secret_in_production(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("AEROGRID_ENV", "production")
    monkeypatch.setenv("AEROGRID_JWT_SECRET", "a-real-production-secret-value")
    assert signing_secret() == "a-real-production-secret-value"


# -- issue_token / decode_token --------------------------------------------


def test_issue_and_decode_roundtrip(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("AEROGRID_JWT_SECRET", raising=False)
    tid = uuid.uuid4()
    token = issue_token(tid, Role.ADMIN)
    ctx = decode_token(token)
    assert ctx.tenant_id == tid
    assert ctx.role is Role.ADMIN
    assert ctx.is_superadmin is False


def test_decode_superadmin_flag(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("AEROGRID_JWT_SECRET", raising=False)
    token = issue_token(uuid.uuid4(), Role.SUPERADMIN)
    ctx = decode_token(token)
    assert ctx.is_superadmin is True


def test_decode_rejects_expired_token(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("AEROGRID_JWT_SECRET", raising=False)
    past = datetime.now(UTC) - timedelta(days=1)
    token = issue_token(uuid.uuid4(), Role.VIEWER, ttl_seconds=1, now=past)
    with pytest.raises(HTTPException) as excinfo:
        decode_token(token)
    assert excinfo.value.status_code == 401
    assert "expired" in excinfo.value.detail


def test_decode_rejects_bad_signature(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AEROGRID_JWT_SECRET", "signing-secret-one-long-enough-for-hs256")
    other = jwt.encode(
        {"sub": str(uuid.uuid4()), "role": "viewer"},
        "different-secret-long-enough-for-hs256",
        algorithm=ALGORITHM,
    )
    with pytest.raises(HTTPException) as excinfo:
        decode_token(other)
    assert excinfo.value.status_code == 401


def test_decode_rejects_missing_sub(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AEROGRID_JWT_SECRET", "test-secret-which-is-long-enough-for-hs256")
    token = jwt.encode(
        {"role": "viewer"}, "test-secret-which-is-long-enough-for-hs256", algorithm=ALGORITHM
    )
    with pytest.raises(HTTPException, match="missing sub or role"):
        decode_token(token)


def test_decode_rejects_non_uuid_sub(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AEROGRID_JWT_SECRET", "test-secret-which-is-long-enough-for-hs256")
    token = jwt.encode(
        {"sub": "not-a-uuid", "role": "viewer"},
        "test-secret-which-is-long-enough-for-hs256",
        algorithm=ALGORITHM,
    )
    with pytest.raises(HTTPException, match="not a UUID"):
        decode_token(token)


def test_decode_rejects_unknown_role(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AEROGRID_JWT_SECRET", "test-secret-which-is-long-enough-for-hs256")
    token = jwt.encode(
        {"sub": str(uuid.uuid4()), "role": "god"},
        "test-secret-which-is-long-enough-for-hs256",
        algorithm=ALGORITHM,
    )
    with pytest.raises(HTTPException, match="unknown role"):
        decode_token(token)


# -- require_tenant --------------------------------------------------------


def _fake_request(headers: dict[str, str]) -> Request:
    """Build a minimal Starlette Request with the given headers."""
    raw = [(k.lower().encode(), v.encode()) for k, v in headers.items()]
    scope = {
        "type": "http",
        "method": "GET",
        "path": "/",
        "headers": raw,
    }
    return Request(scope)


def test_require_tenant_rejects_missing_header(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("AEROGRID_JWT_SECRET", raising=False)
    with pytest.raises(HTTPException) as excinfo:
        require_tenant(_fake_request({}))
    assert excinfo.value.status_code == 401
    assert "missing Authorization" in excinfo.value.detail


def test_require_tenant_rejects_malformed_header(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("AEROGRID_JWT_SECRET", raising=False)
    with pytest.raises(HTTPException):
        require_tenant(_fake_request({"Authorization": "Basic abc123"}))


def test_require_tenant_accepts_valid_header(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("AEROGRID_JWT_SECRET", raising=False)
    tid = uuid.uuid4()
    token = issue_token(tid, Role.VIEWER)
    ctx = require_tenant(
        _fake_request({"Authorization": f"Bearer {token}"}),
    )
    assert ctx.tenant_id == tid
    assert ctx.role is Role.VIEWER


# -- require_role ----------------------------------------------------------


def _request_with_role(monkeypatch: pytest.MonkeyPatch, role: Role) -> Request:
    monkeypatch.delenv("AEROGRID_JWT_SECRET", raising=False)
    token = issue_token(uuid.uuid4(), role)
    return _fake_request({"Authorization": f"Bearer {token}"})


def test_require_role_viewer_passes_viewer_check(monkeypatch: pytest.MonkeyPatch) -> None:
    check = require_role(Role.VIEWER)
    ctx = check(_request_with_role(monkeypatch, Role.VIEWER))
    assert isinstance(ctx, TenantContext)
    assert ctx.role is Role.VIEWER


def test_require_role_viewer_fails_admin_check(monkeypatch: pytest.MonkeyPatch) -> None:
    check = require_role(Role.ADMIN)
    with pytest.raises(HTTPException) as excinfo:
        check(_request_with_role(monkeypatch, Role.VIEWER))
    assert excinfo.value.status_code == 403
    assert "viewer" in excinfo.value.detail
    assert "admin" in excinfo.value.detail


def test_require_role_admin_passes_viewer_check(monkeypatch: pytest.MonkeyPatch) -> None:
    check = require_role(Role.VIEWER)
    ctx = check(_request_with_role(monkeypatch, Role.ADMIN))
    assert ctx.role is Role.ADMIN


def test_require_role_superadmin_passes_admin_check(monkeypatch: pytest.MonkeyPatch) -> None:
    check = require_role(Role.ADMIN)
    ctx = check(_request_with_role(monkeypatch, Role.SUPERADMIN))
    assert ctx.role is Role.SUPERADMIN


def test_require_role_superadmin_passes_superadmin_check(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    check = require_role(Role.SUPERADMIN)
    ctx = check(_request_with_role(monkeypatch, Role.SUPERADMIN))
    assert ctx.is_superadmin is True


def test_require_role_admin_fails_superadmin_check(monkeypatch: pytest.MonkeyPatch) -> None:
    check = require_role(Role.SUPERADMIN)
    with pytest.raises(HTTPException) as excinfo:
        check(_request_with_role(monkeypatch, Role.ADMIN))
    assert excinfo.value.status_code == 403


# Avoid unused-import lint on Headers.
_ = Headers
