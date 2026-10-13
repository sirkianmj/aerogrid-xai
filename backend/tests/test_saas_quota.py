"""Tests for the quota store and consume() enforcement.

Two layers of coverage:

  * Pure unit tests of Metric, Plan, PLAN_LIMITS, the period helpers,
    plan_for_status, FakeQuotaStore, and consume(). These run in the
    default backend CI job without a database.

  * PostgresQuotaStore integration tests. They are guarded by a
    function-level skip so a missing database only skips those tests,
    not the whole module. In the rls-isolation CI job the database is
    present, so those tests run and the job's fail-on-skip assertion
    is satisfied.
"""

from __future__ import annotations

import uuid
from collections.abc import Iterator
from datetime import UTC, date, datetime

import pytest
from fastapi import HTTPException
from sqlalchemy import text

from app.saas.db import admin_session, get_engine
from app.saas.quota import (
    PLAN_LIMITS,
    FakeQuotaStore,
    Metric,
    Plan,
    PostgresQuotaStore,
    QuotaStore,
    consume,
    current_period_start,
    next_period_start,
    plan_for_status,
)

# --- pure unit tests ------------------------------------------------------


def test_metric_values() -> None:
    assert Metric.Z3_SOLVES.value == "z3_solves"
    assert Metric.TRADESPACE_RUNS.value == "tradespace_runs"
    assert Metric.CLEAR_D_RUNS.value == "clear_d_runs"


def test_plan_values() -> None:
    assert Plan.FREE.value == "free"
    assert Plan.PRO.value == "pro"
    assert Plan.ENTERPRISE.value == "enterprise"


def test_plan_limits_cover_every_plan_and_metric() -> None:
    for plan in Plan:
        assert plan in PLAN_LIMITS
        for metric in Metric:
            assert metric in PLAN_LIMITS[plan]
            assert PLAN_LIMITS[plan][metric] > 0


def test_plan_limits_are_monotone_across_plans() -> None:
    order = [Plan.FREE, Plan.PRO, Plan.ENTERPRISE]
    for metric in Metric:
        values = [PLAN_LIMITS[p][metric] for p in order]
        assert values == sorted(values)


def test_current_period_start_uses_utc_month() -> None:
    assert current_period_start(datetime(2026, 3, 15, 12, 0, tzinfo=UTC)) == date(2026, 3, 1)
    assert current_period_start(datetime(2026, 12, 31, 23, 59, tzinfo=UTC)) == date(2026, 12, 1)


def test_next_period_start_rolls_over_year() -> None:
    assert next_period_start(date(2026, 3, 1)) == date(2026, 4, 1)
    assert next_period_start(date(2026, 12, 1)) == date(2027, 1, 1)


def test_plan_for_status_active_and_trialing_are_pro() -> None:
    assert plan_for_status("active") == Plan.PRO
    assert plan_for_status("trialing") == Plan.PRO


def test_plan_for_status_other_states_are_free() -> None:
    for status in (None, "canceled", "unpaid", "past_due", "incomplete"):
        assert plan_for_status(status) == Plan.FREE


def test_fake_store_starts_empty() -> None:
    store = FakeQuotaStore()
    tid = uuid.uuid4()
    assert store.peek(tid, Metric.TRADESPACE_RUNS, current_period_start()) == 0


def test_fake_store_increment_returns_new_count() -> None:
    store = FakeQuotaStore()
    tid = uuid.uuid4()
    period = current_period_start()
    assert store.increment(tid, Metric.TRADESPACE_RUNS, period) == 1
    assert store.increment(tid, Metric.TRADESPACE_RUNS, period) == 2
    assert store.peek(tid, Metric.TRADESPACE_RUNS, period) == 2


def test_fake_store_is_per_metric_per_tenant_per_period() -> None:
    store = FakeQuotaStore()
    tid_a, tid_b = uuid.uuid4(), uuid.uuid4()
    p1, p2 = date(2026, 3, 1), date(2026, 4, 1)
    store.increment(tid_a, Metric.TRADESPACE_RUNS, p1)
    store.increment(tid_a, Metric.Z3_SOLVES, p1)
    store.increment(tid_a, Metric.TRADESPACE_RUNS, p2)
    store.increment(tid_b, Metric.TRADESPACE_RUNS, p1)
    assert store.peek(tid_a, Metric.TRADESPACE_RUNS, p1) == 1
    assert store.peek(tid_a, Metric.Z3_SOLVES, p1) == 1
    assert store.peek(tid_a, Metric.TRADESPACE_RUNS, p2) == 1
    assert store.peek(tid_b, Metric.TRADESPACE_RUNS, p1) == 1


def test_stores_satisfy_the_protocol() -> None:
    assert isinstance(FakeQuotaStore(), QuotaStore)
    assert isinstance(PostgresQuotaStore(), QuotaStore)


def test_consume_returns_new_count_when_under_limit() -> None:
    store = FakeQuotaStore()
    assert consume(store, uuid.uuid4(), Plan.FREE, Metric.TRADESPACE_RUNS) == 1


def test_consume_raises_429_after_limit_exhausted() -> None:
    store = FakeQuotaStore()
    tid = uuid.uuid4()
    limit = PLAN_LIMITS[Plan.FREE][Metric.TRADESPACE_RUNS]
    for _ in range(limit):
        consume(store, tid, Plan.FREE, Metric.TRADESPACE_RUNS)
    with pytest.raises(HTTPException) as info:
        consume(store, tid, Plan.FREE, Metric.TRADESPACE_RUNS)
    assert info.value.status_code == 429
    assert "Retry-After" in (info.value.headers or {})


def test_consume_charges_even_when_over_limit() -> None:
    store = FakeQuotaStore()
    tid = uuid.uuid4()
    limit = PLAN_LIMITS[Plan.FREE][Metric.TRADESPACE_RUNS]
    for _ in range(limit):
        consume(store, tid, Plan.FREE, Metric.TRADESPACE_RUNS)
    with pytest.raises(HTTPException):
        consume(store, tid, Plan.FREE, Metric.TRADESPACE_RUNS)
    period = current_period_start()
    assert store.peek(tid, Metric.TRADESPACE_RUNS, period) == limit + 1


def test_consume_retry_after_reflects_the_supplied_now() -> None:
    """With now fixed, Retry-After is deterministic.

    From 2026-03-15T12:00Z to 2026-04-01T00:00Z is 16 days and 12 hours
    = 1_425_600 seconds. Allow a one-second tolerance.
    """
    store = FakeQuotaStore()
    tid = uuid.uuid4()
    limit = PLAN_LIMITS[Plan.FREE][Metric.TRADESPACE_RUNS]
    now = datetime(2026, 3, 15, 12, 0, tzinfo=UTC)
    for _ in range(limit):
        consume(store, tid, Plan.FREE, Metric.TRADESPACE_RUNS, now=now)
    with pytest.raises(HTTPException) as info:
        consume(store, tid, Plan.FREE, Metric.TRADESPACE_RUNS, now=now)
    retry_after = int((info.value.headers or {})["Retry-After"])
    expected = int((datetime(2026, 4, 1, 0, 0, tzinfo=UTC) - now).total_seconds())
    assert abs(retry_after - expected) <= 1


def test_consume_isolates_tenants() -> None:
    store = FakeQuotaStore()
    a, b = uuid.uuid4(), uuid.uuid4()
    limit = PLAN_LIMITS[Plan.FREE][Metric.TRADESPACE_RUNS]
    for _ in range(limit):
        consume(store, a, Plan.FREE, Metric.TRADESPACE_RUNS)
    assert consume(store, b, Plan.FREE, Metric.TRADESPACE_RUNS) == 1


# --- Postgres-backed integration tests ------------------------------------


def _postgres_reachable() -> bool:
    try:
        with get_engine().connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False


requires_postgres = pytest.mark.skipif(
    not _postgres_reachable(),
    reason=(
        "PostgreSQL is not reachable; start it with scripts/start_services.sh "
        "and apply backend/app/saas/migrations/003_quota_usage.sql"
    ),
)


@pytest.fixture()
def pg_tenant() -> Iterator[uuid.UUID]:
    tid = uuid.uuid4()
    with admin_session() as s:
        s.execute(
            text("INSERT INTO tenants (id, slug, display_name) VALUES (:i, :s, :n)"),
            {"i": str(tid), "s": f"q-{tid.hex[:8]}", "n": "Quota Test"},
        )
    try:
        yield tid
    finally:
        with admin_session() as s:
            s.execute(text("DELETE FROM tenants WHERE id = :i"), {"i": str(tid)})


@requires_postgres
def test_postgres_store_increment_returns_new_count(pg_tenant: uuid.UUID) -> None:
    store = PostgresQuotaStore()
    period = current_period_start()
    assert store.increment(pg_tenant, Metric.TRADESPACE_RUNS, period) == 1
    assert store.increment(pg_tenant, Metric.TRADESPACE_RUNS, period) == 2
    assert store.peek(pg_tenant, Metric.TRADESPACE_RUNS, period) == 2


@requires_postgres
def test_postgres_store_peek_returns_zero_when_missing(pg_tenant: uuid.UUID) -> None:
    store = PostgresQuotaStore()
    assert store.peek(pg_tenant, Metric.CLEAR_D_RUNS, current_period_start()) == 0
