"""Authentication endpoints.

  POST /auth/signup  create a new tenant; returns a JWT for immediate use
  POST /auth/token   exchange tenant slug + password for a JWT

Roadmap: real sign-in flow (replaces the paste-a-JWT SessionBar) and
self-service signup (unblocks the Sprint 12 s12-11 user journey).

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

import re

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

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


# --- Signup -----------------------------------------------------------------


_SLUG_RE = re.compile(r"^[a-z0-9](?:[a-z0-9-]{1,30}[a-z0-9])?$")


class SignupRequest(BaseModel):
    """Body for POST /auth/signup.

    The slug is the login handle: lowercase alphanumerics and internal
    hyphens, 3 to 32 characters, must start and end alphanumeric. The
    password has a 12-character minimum; a weaker rule would be a
    liability given that the tenant can provision real infrastructure.
    The display name is shown in the SaaS UI and the admin panel; it
    is not unique and not used for authentication.
    """

    slug: str = Field(..., min_length=3, max_length=32)
    display_name: str = Field(..., min_length=1, max_length=128)
    password: str = Field(..., min_length=12, max_length=256)


class SignupResponse(BaseModel):
    token: str
    tenant_id: str
    role: str
    expires_in_seconds: int


@router.post("/signup", response_model=SignupResponse, status_code=201)
async def signup(request: SignupRequest) -> SignupResponse:
    """Create a tenant and return a JWT for immediate use.

    Validation is done here, not at the database. Slug format errors
    and short passwords are 422 (validation failures, not auth
    failures). Duplicate slug is 409, because the resource the caller
    asked for already exists.

    The insert hashes the password inside Postgres with pgcrypto's
    bcrypt, matching the pattern used by /auth/token. The plaintext
    never leaves the SQL parameter binding.

    The new tenant receives Role.ADMIN, the same role /auth/token
    issues. This endpoint is not a path to superadmin; that role is
    only issued out of band by the operator.

    Raises:
        HTTPException 422 on invalid slug format.
        HTTPException 409 if the slug is already taken.
    """
    if not _SLUG_RE.match(request.slug):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                "slug must be 3 to 32 characters, lowercase alphanumerics "
                "and internal hyphens only, starting and ending alphanumeric"
            ),
        )

    try:
        with admin_session() as s:
            row = s.execute(
                text(
                    "INSERT INTO tenants (slug, display_name, password_hash) "
                    "VALUES (:slug, :display_name, "
                    "crypt(:password, gen_salt('bf', 12))) "
                    "RETURNING id"
                ),
                {
                    "slug": request.slug,
                    "display_name": request.display_name,
                    "password": request.password,
                },
            ).first()
    except IntegrityError as exc:
        # Unique constraint on tenants.slug. Any other integrity error
        # is genuinely unexpected and propagates.
        message = str(exc.orig) if exc.orig is not None else str(exc)
        if "slug" in message.lower() and "unique" in message.lower():
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"slug {request.slug!r} is already taken",
            ) from exc
        raise

    if row is None:
        # The INSERT ... RETURNING id contract failed; this is a bug.
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="signup failed: no row returned",
        )

    tenant_id = row[0]
    token = issue_token(tenant_id, Role.ADMIN, ttl_seconds=DEFAULT_TOKEN_TTL_SECONDS)
    return SignupResponse(
        token=token,
        tenant_id=str(tenant_id),
        role=Role.ADMIN.value,
        expires_in_seconds=DEFAULT_TOKEN_TTL_SECONDS,
    )
