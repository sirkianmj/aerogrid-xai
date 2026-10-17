"""Per-tenant quota management.

Every expensive operation consumes a quota unit from the tenant's
monthly allowance. The counter lives in PostgreSQL (see migration 003)
and is incremented atomically with the operation it guards, so a
crashed request cannot leak a unit and a concurrent duplicate cannot
double-charge.

Metrics
-------

  z3_solves         one unit per Stage B Z3 check
  tradespace_runs   one unit per POST /tradespace/run
  clear_d_runs      one unit per CLEAR-D loop run

Cheap reads are not metered.

Plans
-----

A tenant's plan is derived from its subscription status:

  no subscription / 'canceled' / 'unpaid'   Free
  'active' / 'trialing'                     Pro

The plan is resolved by the get_tenant_plan FastAPI dependency and
passed explicitly to consume(). This keeps consume() free of database
access to the tenants table, which lets the quota tests and the
tradespace-route tests override the plan without a database.

PLAN_LIMITS is the plan-to-limit table. Moving it to a `plans` table
later is a one-migration change.

Enforcement
-----------

consume(store, tenant_id, plan, metric) atomically increments the
counter for the current month. If the new count exceeds the plan limit,
it raises HTTPException 429 with a Retry-After header pointing at the
start of the next month. The exception fires after the increment, so an
attempt that is over limit is still counted; a client that repeatedly
attempts over-limit operations sees its counter rise.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from enum import StrEnum
from typing import Protocol, runtime_checkable
from uuid import UUID

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy import text

from app.saas.auth import TenantContext, require_tenant
from app.saas.db import admin_session


class Metric(StrEnum):
    Z3_SOLVES = "z3_solves"
    TRADESPACE_RUNS = "tradespace_runs"
    CLEAR_D_RUNS = "clear_d_runs"


class Plan(StrEnum):
    FREE = "free"
    PRO = "pro"
    ENTERPRISE = "enterprise"


PLAN_LIMITS: dict[Plan, dict[Metric, int]] = {
    Plan.FREE: {
        Metric.Z3_SOLVES: 200,
        Metric.TRADESPACE_RUNS: 10,
        Metric.CLEAR_D_RUNS: 2,
    },
    Plan.PRO: {
        Metric.Z3_SOLVES: 20_000,
        Metric.TRADESPACE_RUNS: 500,
        Metric.CLEAR_D_RUNS: 200,
    },
    Plan.ENTERPRISE: {
        Metric.Z3_SOLVES: 1_000_000,
        Metric.TRADESPACE_RUNS: 100_000,
        Metric.CLEAR_D_RUNS: 100_000,
    },
}


def current_period_start(now: datetime | None = None) -> date:
    """Return the first day of the current UTC month."""
    n = now or datetime.now(UTC)
    return date(n.year, n.month, 1)


def next_period_start(period: date) -> date:
    """Return the first day of the month after the given one."""
    if period.month == 12:
        return date(period.year + 1, 1, 1)
    return date(period.year, period.month + 1, 1)


def plan_for_status(subscription_status: str | None) -> Plan:
    """Map a Stripe subscription status to a plan."""
    if subscription_status in ("active", "trialing"):
        return Plan.PRO
    return Plan.FREE


@runtime_checkable
class QuotaStore(Protocol):
    """Protocol for a per-tenant quota counter store."""

    def increment(self, tenant_id: UUID, metric: Metric, period: date) -> int:
        """Atomically increment the counter and return the new value."""
        ...

    def peek(self, tenant_id: UUID, metric: Metric, period: date) -> int:
        """Return the current count without modifying it."""
        ...


class PostgresQuotaStore:
    """Quota store backed by the quota_usage table."""

    def increment(self, tenant_id: UUID, metric: Metric, period: date) -> int:
        with admin_session() as s:
            row = s.execute(
                text(
                    "INSERT INTO quota_usage "
                    "(tenant_id, metric, period_start, count) "
                    "VALUES (:t, :m, :p, 1) "
                    "ON CONFLICT (tenant_id, metric, period_start) "
                    "DO UPDATE SET count = quota_usage.count + 1 "
                    "RETURNING count"
                ),
                {"t": str(tenant_id), "m": metric.value, "p": period},
            ).first()
        assert row is not None
        return int(row[0])

    def peek(self, tenant_id: UUID, metric: Metric, period: date) -> int:
        with admin_session() as s:
            row = s.execute(
                text(
                    "SELECT count FROM quota_usage "
                    "WHERE tenant_id = :t AND metric = :m AND period_start = :p"
                ),
                {"t": str(tenant_id), "m": metric.value, "p": period},
            ).first()
        return int(row[0]) if row is not None else 0


@dataclass
class FakeQuotaStore:
    """In-memory quota store for tests. Not thread-safe."""

    _counts: dict[tuple[str, str, date], int] = field(default_factory=dict)

    def increment(self, tenant_id: UUID, metric: Metric, period: date) -> int:
        key = (str(tenant_id), metric.value, period)
        self._counts[key] = self._counts.get(key, 0) + 1
        return self._counts[key]

    def peek(self, tenant_id: UUID, metric: Metric, period: date) -> int:
        key = (str(tenant_id), metric.value, period)
        return self._counts.get(key, 0)


def _is_desktop_mode() -> bool:
    return os.environ.get("AEROGRID_DESKTOP") == "1"


class NoOpQuotaStore:
    """A quota store that does nothing. Used in desktop mode."""

    def increment(self, tenant_id: UUID, metric: Metric, period: date) -> int:
        return 0

    def peek(self, tenant_id: UUID, metric: Metric, period: date) -> int:
        return 0


def get_tenant_plan(ctx: TenantContext = Depends(require_tenant)) -> Plan:
    """FastAPI dependency: resolve the caller's plan from the tenants table.

    Raises:
        HTTPException 404 if the tenant row does not exist.

    In desktop mode returns Plan.PRO without touching the database.
    """
    if _is_desktop_mode():
        return Plan.PRO
    with admin_session() as s:
        row = s.execute(
            text("SELECT stripe_subscription_status FROM tenants WHERE id = :i"),
            {"i": str(ctx.tenant_id)},
        ).first()
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"tenant {ctx.tenant_id} not found",
        )
    return plan_for_status(row[0])


def get_quota_store(request: Request) -> QuotaStore:
    """FastAPI dependency: return the app-wide quota store.

    Lazily instantiated as a PostgresQuotaStore on first use. Tests
    override by setting app.dependency_overrides[get_quota_store].

    In desktop mode returns a no-op store.
    """
    if _is_desktop_mode():
        return NoOpQuotaStore()
    store: QuotaStore | None = getattr(request.app.state, "quota_store", None)
    if store is None:
        store = PostgresQuotaStore()
        request.app.state.quota_store = store
    return store


def consume(
    store: QuotaStore,
    tenant_id: UUID,
    plan: Plan,
    metric: Metric,
    *,
    now: datetime | None = None,
) -> int:
    """Consume one quota unit for a tenant and metric.

    Returns the new count. Raises HTTPException 429 with Retry-After if
    the plan limit for the metric has been exceeded by this call. The
    increment happens before the check.
    """
    limit = PLAN_LIMITS[plan][metric]
    reference = now or datetime.now(UTC)
    period = current_period_start(reference)
    new_count = store.increment(tenant_id, metric, period)
    if new_count > limit:
        retry_at = next_period_start(period)
        seconds = int(
            (
                datetime.combine(retry_at, datetime.min.time(), tzinfo=UTC) - reference
            ).total_seconds()
        )
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=(
                f"quota exceeded for {metric.value} on plan {plan.value}: "
                f"{new_count} > {limit} for period starting {period.isoformat()}"
            ),
            headers={"Retry-After": str(max(seconds, 1))},
        )
    return new_count
