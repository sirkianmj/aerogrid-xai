"""HTTP admin routes for tenant management and usage dashboards.

Two endpoints under /saas/admin, both requiring the superadmin role:

    GET /saas/admin/tenants
        List every tenant with its plan and subscription status.

    GET /saas/admin/tenants/{tenant_id}/usage
        Per-metric quota usage for the current calendar month.

Both endpoints use admin_session, which runs as the database superuser
and bypasses RLS. That is correct for an admin surface: the caller is
authenticated as a superadmin (require_role(Role.SUPERADMIN)) and is
explicitly authorized to see across tenants. No tenant_session is used,
so the app.tenant_id GUC is never set and the RLS policy is not part of
the query path. The WHERE clauses in this module are the only filters
and they are always present.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import text

from app.saas.auth import Role, TenantContext, require_role
from app.saas.db import admin_session
from app.saas.quota import (
    PLAN_LIMITS,
    Metric,
    current_period_start,
    plan_for_status,
)

router = APIRouter(prefix="/saas/admin", tags=["saas-admin"])


class TenantSummary(BaseModel):
    id: str
    slug: str
    display_name: str
    created_at: str
    stripe_subscription_status: str | None
    plan: str


class TenantListResponse(BaseModel):
    tenants: list[TenantSummary]
    count: int


@router.get("/tenants", response_model=TenantListResponse)
async def list_tenants(
    _ctx: TenantContext = Depends(require_role(Role.SUPERADMIN)),
) -> TenantListResponse:
    """List every tenant. Superadmin only.

    Reads through admin_session, which is a superuser session and
    therefore bypasses RLS on the missions and quota_usage tables. The
    tenants table has no RLS policy; the SELECT below is cross-tenant by
    design and the caller has been verified to be a superadmin.
    """
    with admin_session() as s:
        rows = s.execute(
            text(
                "SELECT id, slug, display_name, created_at, "
                "stripe_subscription_status "
                "FROM tenants ORDER BY created_at, id"
            )
        ).all()
    tenants = [
        TenantSummary(
            id=str(r[0]),
            slug=r[1],
            display_name=r[2],
            created_at=r[3].isoformat(),
            stripe_subscription_status=r[4],
            plan=plan_for_status(r[4]).value,
        )
        for r in rows
    ]
    return TenantListResponse(tenants=tenants, count=len(tenants))


class MetricUsage(BaseModel):
    metric: str
    count: int
    limit: int


class TenantUsageResponse(BaseModel):
    tenant_id: str
    period_start: str
    plan: str
    usage: list[MetricUsage]


@router.get("/tenants/{tenant_id}/usage", response_model=TenantUsageResponse)
async def tenant_usage(
    tenant_id: str,
    _ctx: TenantContext = Depends(require_role(Role.SUPERADMIN)),
) -> TenantUsageResponse:
    """Return per-metric quota usage for the current calendar month.

    Superadmin only. Every metric defined in the Plan model is included,
    with a count of zero if the tenant has not consumed any units. A
    404 is raised if the tenant row does not exist, so a caller cannot
    use this endpoint as a probe for UUID existence.
    """
    with admin_session() as s:
        tenant_row = s.execute(
            text("SELECT stripe_subscription_status FROM tenants WHERE id = :i"),
            {"i": tenant_id},
        ).first()
        if tenant_row is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"tenant {tenant_id} not found",
            )
        plan = plan_for_status(tenant_row[0])

        period = current_period_start()
        usage_rows = s.execute(
            text(
                "SELECT metric, count FROM quota_usage WHERE tenant_id = :t AND period_start = :p"
            ),
            {"t": tenant_id, "p": period},
        ).all()

    usage_by_metric = {str(r[0]): int(r[1]) for r in usage_rows}
    usage = [
        MetricUsage(
            metric=m.value,
            count=usage_by_metric.get(m.value, 0),
            limit=PLAN_LIMITS[plan][m],
        )
        for m in Metric
    ]
    return TenantUsageResponse(
        tenant_id=tenant_id,
        period_start=period.isoformat(),
        plan=plan.value,
        usage=usage,
    )
