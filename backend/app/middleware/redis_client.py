"""Shared Redis client for the rate limiter.

Lazy singleton with a failure cooldown. When Redis is unavailable, the
rate limiter degrades per a documented policy (see rate_limit.py):
fail closed for authentication routes, fail open everywhere else.

The cooldown prevents the middleware from attempting a TCP connect on
every request while Redis is down. When the cooldown expires, the next
request tries again, and if Redis has come back, the limiter resumes.
"""

from __future__ import annotations

import os
import time

import redis
from redis import Redis

_CLIENT: Redis | None = None
_LAST_FAILURE_TS: float = 0.0
_FAILURE_COOLDOWN_S: float = 30.0


def _url() -> str:
    return os.environ.get("AEROGRID_REDIS_URL", "redis://127.0.0.1:6379/0")


def get_redis() -> Redis | None:
    """Return a connected Redis client, or None if Redis is unavailable.

    The first successful call caches the client for the process lifetime.
    Failures are cached for ``_FAILURE_COOLDOWN_S`` seconds so the
    middleware does not pay a connection-timeout cost on every request.
    """
    global _CLIENT, _LAST_FAILURE_TS
    if _CLIENT is not None:
        return _CLIENT
    now = time.time()
    if now - _LAST_FAILURE_TS < _FAILURE_COOLDOWN_S:
        return None
    try:
        client: Redis = redis.from_url(  # type: ignore[no-untyped-call]
            _url(),
            decode_responses=True,
            socket_connect_timeout=1.0,
            socket_timeout=1.0,
        )
        client.ping()
        _CLIENT = client
        return _CLIENT
    except Exception:
        _LAST_FAILURE_TS = now
        return None
