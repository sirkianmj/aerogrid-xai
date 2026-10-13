"""HTTP routes that expose tenant identity.

Two routes:

  GET /saas/whoami    echoes the caller's tenant and role
  GET /saas/echo-mission  returns the number of missions the caller
                          can see, demonstrating that the RLS-scoped
                          session is what the request handler uses

Both routes require a valid JWT. The whoami route accepts any role; the
echo-mission route requires at least viewer.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import text

from app.saas.auth import Role, TenantContext, require_role, require_tenant
from app.saas.db import tenant_session

router = APIRouter(prefix="/saas", tags=["saas"])


class WhoAmIResponse(BaseModel):
    tenant_id: str
    role: str
    is_superadmin: bool


@router.get("/whoami", response_model=WhoAmIResponse)
async def whoami(ctx: TenantContext = Depends(require_tenant)) -> WhoAmIResponse:
    """Return the resolved tenant identity for the caller.

    Demonstrates that the JWT is decoded and the tenant context is
    available to request handlers.
    """
    return WhoAmIResponse(
        tenant_id=str(ctx.tenant_id),
        role=ctx.role.value,
        is_superadmin=ctx.is_superadmin,
    )


class MissionCountResponse(BaseModel):
    tenant_id: str
    role: str
    n_missions: int


@router.get("/mission-count", response_model=MissionCountResponse)
async def mission_count(
    ctx: TenantContext = Depends(require_role(Role.VIEWER)),
) -> MissionCountResponse:
    """Return the number of missions visible to the caller.

    The count comes from a tenant_session, which issues SET LOCAL ROLE
    aerogrid_app and sets app.tenant_id. PostgreSQL row-level security
    filters the query to the caller's tenant. The count therefore
    reflects what the database permits, not what the handler requests.
    """
    with tenant_session(ctx.tenant_id) as s:
        n = s.execute(text("SELECT COUNT(*) FROM missions")).scalar() or 0
    return MissionCountResponse(
        tenant_id=str(ctx.tenant_id),
        role=ctx.role.value,
        n_missions=int(n),
    )
