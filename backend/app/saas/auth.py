"""Tenant authentication and authorization.

A request carries a JWT in the ``Authorization: Bearer <token>`` header.
The token's ``sub`` claim is the tenant UUID; the ``role`` claim is one
of ``viewer``, ``admin``, or ``superadmin``. The middleware decodes the
token, resolves the tenant, and stashes a per-request tenant context
into ``request.state``.

Signing secret
--------------

Read from ``AEROGRID_JWT_SECRET`` in the environment. If the environment
is ``development`` (``AEROGRID_ENV=development``), a documented default
secret is used so that a fresh checkout runs without setup. If the
environment is anything else and the secret is unset or equals the
development default, the process refuses to start. This prevents the
"shipped the dev secret to production" failure mode.

Token format
------------

Standard HS256 JWT. Claims:

  sub   tenant UUID (string)
  role  one of viewer, admin, superadmin
  exp   expiry, Unix seconds
  iat   issued at, Unix seconds

Issuing tokens is the responsibility of the tenant provisioning path
(s8-7 admin panel) and of tests. This module only verifies them.

Roles
-----

  viewer       read-only access to tenant-scoped resources
  admin        read and write within the tenant
  superadmin   cross-tenant access, used by the admin panel and
               by provisioning

Superadmin bypasses the tenant filter. Admin and viewer do not.
"""

from __future__ import annotations

import os
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from uuid import UUID

import jwt
from fastapi import HTTPException, Request, status

DEV_SECRET = "aerogrid-dev-secret-do-not-use-in-production"
"""Default secret used only when AEROGRID_ENV=development."""

ALGORITHM = "HS256"


class Role(StrEnum):
    VIEWER = "viewer"
    ADMIN = "admin"
    SUPERADMIN = "superadmin"


@dataclass(frozen=True)
class TenantContext:
    """Resolved identity of the caller for one request."""

    tenant_id: UUID
    role: Role

    @property
    def is_superadmin(self) -> bool:
        return self.role is Role.SUPERADMIN


def signing_secret() -> str:
    """Return the JWT signing secret for this process.

    Raises:
        RuntimeError if the environment is not development and the
            secret is unset or equals the development default.
    """
    env = os.environ.get("AEROGRID_ENV", "development")
    secret = os.environ.get("AEROGRID_JWT_SECRET")
    if env == "development":
        return secret or DEV_SECRET
    if not secret:
        raise RuntimeError("AEROGRID_JWT_SECRET must be set when AEROGRID_ENV is not 'development'")
    if secret == DEV_SECRET:
        raise RuntimeError(
            "AEROGRID_JWT_SECRET is set to the development default; "
            "generate a real secret before deploying"
        )
    return secret


def issue_token(
    tenant_id: UUID,
    role: Role,
    *,
    ttl_seconds: int = 86_400,
    now: datetime | None = None,
) -> str:
    """Return a signed JWT for one tenant and role.

    Used by the tenant-provisioning path and by tests. Not used by
    request handlers.
    """
    issued = now or datetime.now(UTC)
    payload = {
        "sub": str(tenant_id),
        "role": role.value,
        "iat": int(issued.timestamp()),
        "exp": int((issued + timedelta(seconds=ttl_seconds)).timestamp()),
    }
    return jwt.encode(payload, signing_secret(), algorithm=ALGORITHM)


def decode_token(token: str) -> TenantContext:
    """Decode and validate a JWT, returning the tenant context.

    Raises:
        HTTPException 401 for any token that fails verification.
    """
    try:
        payload = jwt.decode(token, signing_secret(), algorithms=[ALGORITHM])
    except jwt.ExpiredSignatureError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="token expired",
        ) from exc
    except jwt.InvalidTokenError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"invalid token: {exc}",
        ) from exc

    sub = payload.get("sub")
    role_raw = payload.get("role")
    if not isinstance(sub, str) or not isinstance(role_raw, str):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="token is missing sub or role claim",
        )
    try:
        tenant_id = UUID(sub)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"sub claim is not a UUID: {sub}",
        ) from exc
    try:
        role = Role(role_raw)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"unknown role: {role_raw}",
        ) from exc

    return TenantContext(tenant_id=tenant_id, role=role)


def _extract_bearer(request: Request) -> str | None:
    header = request.headers.get("authorization")
    if not header:
        return None
    parts = header.split(None, 1)
    if len(parts) != 2 or parts[0].lower() != "bearer":
        return None
    return parts[1].strip() or None


def require_tenant(request: Request) -> TenantContext:
    """FastAPI dependency: return the caller's tenant context.

    Raises:
        HTTPException 401 if no Authorization: Bearer header is present
            or the token is invalid.
    """
    token = _extract_bearer(request)
    if token is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="missing Authorization: Bearer <token> header",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return decode_token(token)


def require_role(minimum: Role) -> Callable[[Request], TenantContext]:
    """FastAPI dependency factory: require at least the given role.

    Role ordering: viewer < admin < superadmin. A superadmin passes
    every check. An admin passes admin and viewer checks. A viewer
    passes only viewer checks.

    Returns a callable suitable for use as a FastAPI dependency:

        @router.get("/admin-only")
        async def admin_only(
            ctx: TenantContext = Depends(require_role(Role.ADMIN)),
        ) -> ...:
            ...
    """
    order = {Role.VIEWER: 0, Role.ADMIN: 1, Role.SUPERADMIN: 2}
    needed = order[minimum]

    def _check(request: Request) -> TenantContext:
        ctx = require_tenant(request)
        if order[ctx.role] < needed:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"role {ctx.role.value} is below the required {minimum.value}",
            )
        return ctx

    return _check
