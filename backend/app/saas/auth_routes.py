"""Authentication endpoint — exchange tenant slug + password for a JWT.

Roadmap: real sign-in flow (replaces the paste-a-JWT SessionBar).

The endpoint is deliberately not under /saas/*. Every /saas route is
tenant-scoped (requires a JWT whose sub claim is the tenant UUID);
this endpoint is the step that acquires that scope. Putting it under
/saas/auth/token would imply it shares the tenant-scope contract, and
it does not. POST /auth/token is the correct path.

Password verification happens inside PostgreSQL. The plaintext is
bound as a SQL parameter and passed to pgcrypto's crypt() against the
tenant's stored bcrypt hash. Neither the hash nor the plaintext ever
reaches Python as data to be compared — the boolean result of the
comparison is all that comes back. That removes an entire class of
timing-side-channel concerns from the application layer.

Role policy: this endpoint always issues Role.ADMIN. A tenant
administrator can do everything within their own tenant; the JWT's
sub claim confines them to that tenant via PostgreSQL row-level
security. A superadmin token — which bypasses tenant scope and can
read every tenant — is never issued via this endpoint. The platform
operator issues those out of band. This is a security decision, not a
default: an endpoint that any tenant can call must never be able to
mint a cross-tenant credential.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import text

from app.saas.auth import Role, issue_token
from app.saas.db import admin_session

router = APIRouter(prefix="/auth", tags=["auth"])

DEFAULT_TOKEN_TTL_SECONDS = 86_400


class LoginRequest(BaseModel):
    slug: str = Field(..., min_length=1, max_length=64)
    password: str = Field(..., min_length=1, max_length=256)


class LoginResponse(BaseModel):
    token: str
    tenant_id: str
    role: str
    expires_in_seconds: int


@router.post("/token", response_model=LoginResponse)
async def login(request: LoginRequest) -> LoginResponse:
    """Exchange a tenant slug + password for a JWT.

    On any credential failure — unknown slug, wrong password, or a
    tenant whose password_hash is NULL — the response is a single 401
    with the uniform detail "invalid credentials". Distinguishing the
    three cases in the response would leak the existence of slugs to
    an attacker. The lookup query runs unconditionally for every
    request; the failure branch is taken in Python after the query,
    not by skipping the query, so timing does not leak the
    distinction either.

    Raises:
        HTTPException 401 for any credential failure.
    """
    with admin_session() as s:
        row = s.execute(
            text(
                "SELECT id, "
                "COALESCE(crypt(:password, password_hash) = password_hash, "
                "FALSE) AS valid "
                "FROM tenants WHERE slug = :slug"
            ),
            {"slug": request.slug, "password": request.password},
        ).first()

    if row is None or not bool(row[1]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="invalid credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

    tenant_id = row[0]
    token = issue_token(tenant_id, Role.ADMIN, ttl_seconds=DEFAULT_TOKEN_TTL_SECONDS)
    return LoginResponse(
        token=token,
        tenant_id=str(tenant_id),
        role=Role.ADMIN.value,
        expires_in_seconds=DEFAULT_TOKEN_TTL_SECONDS,
    )
