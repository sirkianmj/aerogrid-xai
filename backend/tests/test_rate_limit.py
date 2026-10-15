"""Rate limiting and the fail-open / fail-closed policy.

The tests inject a fake Redis so they do not require a running Redis
instance, and they patch the get_redis lookup used by the middleware so
the failure branches can be exercised.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


class FakeRedis:
    def __init__(self) -> None:
        self.store: dict[str, int] = {}

    def incr(self, key: str) -> int:
        self.store[key] = self.store.get(key, 0) + 1
        return self.store[key]

    def expire(self, _key: str, _ttl: int) -> bool:
        return True


@pytest.fixture(autouse=True)
def _enable_rate_limit(monkeypatch: pytest.MonkeyPatch) -> None:
    """The CI workflow sets AEROGRID_DISABLE_RATE_LIMIT=1 so that the
    broader suite does not trip the fail-closed policy. This fixture
    removes it for every test in this module, so the tests here
    exercise the real limiter."""
    monkeypatch.delenv("AEROGRID_DISABLE_RATE_LIMIT", raising=False)


@pytest.fixture
def fake_redis(monkeypatch: pytest.MonkeyPatch) -> Iterator[FakeRedis]:
    fake = FakeRedis()
    monkeypatch.setattr("app.middleware.rate_limit.get_redis", lambda: fake)
    yield fake


@pytest.fixture
def fake_auth_db(monkeypatch: pytest.MonkeyPatch) -> None:
    """Replace the admin_session used by auth_routes so /auth/signup and
    /auth/token run to completion without PostgreSQL. Returns a UUID and
    a truthy validator for any query, which satisfies both the
    INSERT...RETURNING id and the SELECT id, valid paths."""
    import uuid as _uuid
    from contextlib import contextmanager

    class _Row:
        def __init__(self, values: list[object]) -> None:
            self._v = values

        def __getitem__(self, i: int) -> object:
            return self._v[i]

    class _Result:
        def __init__(self, values: list[object]) -> None:
            self._r = _Row(values)

        def first(self) -> _Row:
            return self._r

    class _Session:
        def execute(
            self,
            _stmt: object,
            _params: object = None,
        ) -> _Result:
            return _Result([_uuid.uuid4(), True])

    @contextmanager
    def _session() -> Iterator[_Session]:
        yield _Session()

    monkeypatch.setattr("app.saas.auth_routes.admin_session", _session)


def test_signup_rate_limit_returns_429_after_threshold(
    fake_redis: FakeRedis, fake_auth_db: None
) -> None:
    payload = {
        "slug": "ratelimit-test",
        "display_name": "Rate Limit Test",
        "password": "correct-horse-battery-staple",
    }
    # First 3 requests get through the limiter (their status codes are
    # whatever the endpoint returns; only the 4th is checked for 429).
    for _ in range(3):
        client.post("/auth/signup", json=payload)
    r = client.post("/auth/signup", json=payload)
    assert r.status_code == 429
    assert r.headers["Retry-After"].isdigit()
    assert r.headers["X-RateLimit-Limit"] == "3"
    assert r.headers["X-RateLimit-Remaining"] == "0"


def test_token_rate_limit_returns_429_after_threshold(
    fake_redis: FakeRedis, fake_auth_db: None
) -> None:
    payload = {"slug": "does-not-exist", "password": "does-not-matter-x"}
    for _ in range(5):
        client.post("/auth/token", json=payload)
    r = client.post("/auth/token", json=payload)
    assert r.status_code == 429


def test_exempt_paths_never_rate_limited(fake_redis: FakeRedis) -> None:
    """The /health probe must always respond, even after hundreds of
    calls; otherwise a liveness checker with a short interval would
    mark the service unhealthy during a benign burst."""
    for _ in range(50):
        r = client.get("/health")
        assert r.status_code == 200


def test_stripe_webhook_is_exempt(fake_redis: FakeRedis) -> None:
    """Stripe retries webhooks on any non-2xx response. Rate-limiting
    the webhook would eventually cause Stripe to disable it."""
    for _ in range(30):
        r = client.post("/saas/billing/webhook/stripe", json={})
        assert r.status_code != 429


def test_auth_fails_closed_when_redis_unavailable(
    monkeypatch: pytest.MonkeyPatch, fake_auth_db: None
) -> None:
    monkeypatch.setattr("app.middleware.rate_limit.get_redis", lambda: None)
    r = client.post(
        "/auth/token",
        json={"slug": "x", "password": "y-not-long-enough"},
    )
    assert r.status_code == 503
    assert "temporarily unavailable" in r.json()["detail"]


def test_reads_fail_open_when_redis_unavailable(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.middleware.rate_limit.get_redis", lambda: None)
    r = client.get("/mission/state")
    assert r.status_code != 503


def test_rate_limit_headers_present_on_allowed_request(fake_redis: FakeRedis) -> None:
    # /discovery/sensitivity is in the rule table at 30/min.
    r = client.post("/discovery/sensitivity", json={"base": {}})
    assert r.headers.get("X-RateLimit-Limit") == "30"
