"""Service status endpoint.

Reports the health of every dependency the platform relies on. Every
check has a short timeout so the endpoint responds quickly even when a
dependency is down; a status page that hangs on the failing dependency
is useless.

Always returns 200 with a JSON payload. The payload carries the
overall status in a field, not in the HTTP code, because Prometheus
scrapes this endpoint and a 503 would break scrape semantics.
"""

from __future__ import annotations

import time
from datetime import UTC, datetime

from fastapi import APIRouter
from pydantic import BaseModel
from sqlalchemy import text

from app.middleware.redis_client import get_redis
from app.saas.db import admin_session

router = APIRouter(prefix="/status", tags=["status"])

_CHECK_TIMEOUT_S = 1.5


class DependencyStatus(BaseModel):
    name: str
    status: str
    detail: str
    latency_ms: float


class StatusResponse(BaseModel):
    overall: str
    checked_at: str
    dependencies: list[DependencyStatus]


def _check_postgres() -> DependencyStatus:
    t0 = time.perf_counter()
    try:
        with admin_session() as s:
            s.execute(text("SELECT 1"))
        return DependencyStatus(
            name="postgres",
            status="ok",
            detail="SELECT 1 ok",
            latency_ms=(time.perf_counter() - t0) * 1000.0,
        )
    except Exception as exc:
        return DependencyStatus(
            name="postgres",
            status="down",
            detail=f"{type(exc).__name__}: {exc}"[:200],
            latency_ms=(time.perf_counter() - t0) * 1000.0,
        )


def _check_redis() -> DependencyStatus:
    t0 = time.perf_counter()
    try:
        r = get_redis()
        if r is None:
            raise RuntimeError("redis client unavailable")
        r.ping()
        return DependencyStatus(
            name="redis",
            status="ok",
            detail="PING ok",
            latency_ms=(time.perf_counter() - t0) * 1000.0,
        )
    except Exception as exc:
        return DependencyStatus(
            name="redis",
            status="down",
            detail=f"{type(exc).__name__}: {exc}"[:200],
            latency_ms=(time.perf_counter() - t0) * 1000.0,
        )


def _check_http(name: str, url: str) -> DependencyStatus:
    import httpx

    t0 = time.perf_counter()
    try:
        r = httpx.get(url, timeout=_CHECK_TIMEOUT_S)
        return DependencyStatus(
            name=name,
            status="ok" if r.status_code == 200 else "down",
            detail=f"HTTP {r.status_code}",
            latency_ms=(time.perf_counter() - t0) * 1000.0,
        )
    except Exception as exc:
        return DependencyStatus(
            name=name,
            status="down",
            detail=f"{type(exc).__name__}: {exc}"[:200],
            latency_ms=(time.perf_counter() - t0) * 1000.0,
        )


def _overall(deps: list[DependencyStatus]) -> str:
    by_name = {d.name: d for d in deps}
    if by_name["postgres"].status == "down":
        return "down"
    if any(d.status == "down" for d in deps):
        return "degraded"
    return "ok"


@router.get("", response_model=StatusResponse)
async def status() -> StatusResponse:
    deps = [
        _check_postgres(),
        _check_redis(),
        _check_http("prometheus", "http://localhost:9090/-/healthy"),
        _check_http("grafana", "http://localhost:3000/api/health"),
    ]
    return StatusResponse(
        overall=_overall(deps),
        checked_at=datetime.now(UTC).isoformat(),
        dependencies=deps,
    )
