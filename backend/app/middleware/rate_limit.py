"""Per-IP rate limiting middleware backed by Redis.

The rule table is fixed and path-based. Every prefix is a real route
that exists in the application today; if a route is removed the entry
here can be removed too, and the middleware simply does not rate-limit
that path.

Policy on Redis availability
----------------------------
- ``/auth/*``: fail **closed** (503). A rate limiter that is down must
  not become a credential-stuffing opportunity. The user sees a
  service-unavailable message and can retry when the platform is
  healthy again.
- Everything else: fail **open** (pass through). A monitoring or cache
  outage must not take down the platform's scientific endpoints.

The middleware uses a fixed window (INCR + EXPIRE) rather than a
sliding window. For a single-user or small-team deployment the
boundary-burst difference is negligible and the fixed window costs one
Redis round trip per request instead of two or three.

Client identity comes from ``request.client.host``. Under the Vite dev
proxy every request appears to come from 127.0.0.1, so the entire dev
session shares one bucket. That is the correct behavior for a single
local user; in production a reverse proxy in front would set the real
client address, and the middleware would need to read it from
``X-Forwarded-For`` after verifying the proxy is trusted.
"""

from __future__ import annotations

import os
import time

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

from app.middleware.redis_client import get_redis

# (prefix, requests, window_seconds). First matching prefix wins.
_RULES: tuple[tuple[str, int, int], ...] = (
    ("/auth/signup", 3, 60),
    ("/auth/token", 5, 60),
    ("/auth/", 20, 60),
    ("/discovery/run", 30, 60),
    ("/discovery/sensitivity", 30, 60),
    ("/design/", 60, 60),
    ("/tradespace/run", 60, 60),
    ("/digital-twin/", 120, 60),
    ("/saas/", 60, 60),
)

# Paths that must never be rate-limited. /saas/billing/webhook/stripe in
# particular is called by Stripe with its own retry policy; rejecting a
# webhook would cause Stripe to retry and eventually disable the
# endpoint.
_EXEMPT: frozenset[str] = frozenset(
    {
        "/health",
        "/metrics",
        "/saas/billing/webhook/stripe",
    }
)


def _rule_for(path: str) -> tuple[str, int, int] | None:
    if path in _EXEMPT:
        return None
    for prefix, limit, window in _RULES:
        if path == prefix or path.startswith(prefix + "/"):
            return prefix, limit, window
    return None


def _client_key(request: Request) -> str:
    if request.client is not None and request.client.host:
        return request.client.host
    return "unknown"


class RateLimitMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):  # type: ignore[no-untyped-def]
        # Test environments do not run Redis. Setting
        # AEROGRID_DISABLE_RATE_LIMIT=1 makes the middleware a no-op so
        # the rest of the test suite can exercise the auth routes
        # without tripping the fail-closed policy. Production and
        # development do not set this.
        if os.environ.get("AEROGRID_DISABLE_RATE_LIMIT") == "1":
            return await call_next(request)
        rule = _rule_for(request.url.path)
        if rule is None:
            return await call_next(request)

        prefix, limit, window = rule
        is_auth = request.url.path.startswith("/auth/")

        redis = get_redis()
        if redis is None:
            if is_auth:
                return JSONResponse(
                    {"detail": "authentication service temporarily unavailable"},
                    status_code=503,
                )
            return await call_next(request)

        bucket = int(time.time() // window)
        key = f"rl:{prefix}:{_client_key(request)}:{bucket}"
        try:
            raw = redis.incr(key)
            # redis-py types incr() as returning Any. Cast through str
            # so the int() overload resolution is unambiguous under
            # mypy --strict.
            count = int(str(raw))
            if count == 1:
                redis.expire(key, window + 1)
        except Exception:
            if is_auth:
                return JSONResponse(
                    {"detail": "authentication service temporarily unavailable"},
                    status_code=503,
                )
            return await call_next(request)

        if count > limit:
            retry_after = window - (int(time.time()) % window)
            return JSONResponse(
                {"detail": "rate limit exceeded"},
                status_code=429,
                headers={
                    "Retry-After": str(retry_after),
                    "X-RateLimit-Limit": str(limit),
                    "X-RateLimit-Remaining": "0",
                },
            )

        response = await call_next(request)
        response.headers["X-RateLimit-Limit"] = str(limit)
        response.headers["X-RateLimit-Remaining"] = str(max(0, limit - count))
        return response
