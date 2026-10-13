"""Tests for the billing routes and the idempotency store.

The route tests use FakeStripeClient and FakeIdempotencyStore set on
app.state, so no network call is made and no real Stripe account is
needed. The tests still exercise the real HMAC signature verification
path because the fake computes an actual Stripe-Signature header.

The tenant fixtures require PostgreSQL with the migrations applied; the
whole module skips if the database is not reachable.
"""

from __future__ import annotations

import json
import time
import uuid
from collections.abc import Iterator

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.main import app as fastapi_app
from app.saas.auth import Role, issue_token
from app.saas.db import admin_session, get_engine
from app.saas.fake_stripe import FakeStripeClient
from app.saas.idempotency import FakeIdempotencyStore, IdempotencyStore

client = TestClient(fastapi_app)


def _postgres_reachable() -> bool:
    try:
        with get_engine().connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False


pytestmark = pytest.mark.skipif(
    not _postgres_reachable(),
    reason=(
        "PostgreSQL is not reachable; start it with scripts/start_services.sh "
        "and apply the migrations under backend/app/saas/migrations/"
    ),
)


# -- fixtures --------------------------------------------------------------


@pytest.fixture(autouse=True)
def _clear_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("AEROGRID_JWT_SECRET", raising=False)
    monkeypatch.delenv("AEROGRID_ENV", raising=False)


@pytest.fixture()
def billing_app() -> Iterator[tuple[FastAPI, FakeStripeClient, FakeIdempotencyStore]]:
    """Set the fake Stripe client and idempotency store on app.state."""
    fake = FakeStripeClient()
    store = FakeIdempotencyStore()
    fastapi_app.state.stripe_client = fake
    fastapi_app.state.idempotency_store = store
    try:
        yield fastapi_app, fake, store
    finally:
        for attr in ("stripe_client", "idempotency_store"):
            if hasattr(fastapi_app.state, attr):
                delattr(fastapi_app.state, attr)


@pytest.fixture()
def tenant_id() -> Iterator[uuid.UUID]:
    tid = uuid.uuid4()
    with admin_session() as s:
        s.execute(
            text("INSERT INTO tenants (id, slug, display_name) VALUES (:i, :s, :n)"),
            {"i": str(tid), "s": f"bill-{tid.hex[:8]}", "n": "Bill Test"},
        )
    try:
        yield tid
    finally:
        with admin_session() as s:
            s.execute(text("DELETE FROM tenants WHERE id = :i"), {"i": str(tid)})


def _auth(tid: uuid.UUID, role: Role) -> dict[str, str]:
    return {"Authorization": f"Bearer {issue_token(tid, role)}"}


def _read_tenant(tid: uuid.UUID) -> tuple[str | None, str | None]:
    with admin_session() as s:
        row = s.execute(
            text(
                "SELECT stripe_subscription_id, stripe_subscription_status "
                "FROM tenants WHERE id = :i"
            ),
            {"i": str(tid)},
        ).first()
    assert row is not None
    return (row[0], row[1])


# -- FakeIdempotencyStore --------------------------------------------------


def test_fake_store_starts_empty() -> None:
    store = FakeIdempotencyStore()
    assert store.already_seen("evt_1") is False
    assert store.size() == 0


def test_fake_store_records_and_detects() -> None:
    store = FakeIdempotencyStore()
    store.record("evt_1", "checkout.session.completed")
    assert store.already_seen("evt_1") is True
    assert store.size() == 1


def test_fake_store_duplicate_record_is_noop() -> None:
    store = FakeIdempotencyStore()
    store.record("evt_1", "type_a")
    store.record("evt_1", "type_b")
    assert store.size() == 1
    assert store.already_seen("evt_1") is True


def test_fake_store_satisfies_protocol() -> None:
    assert isinstance(FakeIdempotencyStore(), IdempotencyStore)


# -- 503 when no Stripe client --------------------------------------------


def test_checkout_503_without_client(tenant_id: uuid.UUID) -> None:
    """If app.state.stripe_client is unset, the route returns 503."""
    # The billing_app fixture is not used here, so the attribute is not
    # set. The autouse fixture only clears the environment.
    r = client.post(
        "/saas/checkout-session",
        headers=_auth(tenant_id, Role.ADMIN),
    )
    assert r.status_code == 503


def test_webhook_503_without_client() -> None:
    r = client.post(
        "/saas/webhook/stripe",
        content=b"{}",
        headers={"Stripe-Signature": "t=1,v1=abc"},
    )
    assert r.status_code == 503


# -- POST /saas/checkout-session ------------------------------------------


def test_checkout_requires_authentication(
    billing_app: tuple[FastAPI, FakeStripeClient, FakeIdempotencyStore],
) -> None:
    r = client.post("/saas/checkout-session")
    assert r.status_code == 401


def test_checkout_requires_admin_role(
    billing_app: tuple[FastAPI, FakeStripeClient, FakeIdempotencyStore],
    tenant_id: uuid.UUID,
) -> None:
    r = client.post(
        "/saas/checkout-session",
        headers=_auth(tenant_id, Role.VIEWER),
    )
    assert r.status_code == 403


def test_checkout_returns_url_for_admin(
    billing_app: tuple[FastAPI, FakeStripeClient, FakeIdempotencyStore],
    tenant_id: uuid.UUID,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # The route reads price_id from the environment. Set it for this test.
    monkeypatch.setenv("AEROGRID_STRIPE_PRICE_ID", "price_test_checkout")
    _, fake, _ = billing_app
    r = client.post(
        "/saas/checkout-session",
        headers=_auth(tenant_id, Role.ADMIN),
    )
    assert r.status_code == 200
    payload = r.json()
    assert payload["checkout_url"].startswith("https://checkout.stripe.test/")
    assert payload["session_id"].startswith("cs_test_")
    # The route created a customer on the fake and recorded its ID on
    # the tenant row.
    # Subscription is not yet set; only the customer is. The route
    # does not touch the subscription columns until the webhook
    # confirms the checkout.
    assert len(fake.customers) == 1


def test_checkout_503_without_price_id(
    billing_app: tuple[FastAPI, FakeStripeClient, FakeIdempotencyStore],
    tenant_id: uuid.UUID,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("AEROGRID_STRIPE_PRICE_ID", raising=False)
    r = client.post(
        "/saas/checkout-session",
        headers=_auth(tenant_id, Role.ADMIN),
    )
    assert r.status_code == 503


def test_checkout_customer_is_created_once_across_calls(
    billing_app: tuple[FastAPI, FakeStripeClient, FakeIdempotencyStore],
    tenant_id: uuid.UUID,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("AEROGRID_STRIPE_PRICE_ID", "price_test_checkout")
    _, fake, _ = billing_app
    client.post("/saas/checkout-session", headers=_auth(tenant_id, Role.ADMIN))
    client.post("/saas/checkout-session", headers=_auth(tenant_id, Role.ADMIN))
    # Second call reuses the customer created by the first.
    assert len(fake.customers) == 1


# -- GET /saas/subscription -----------------------------------------------


def test_subscription_requires_authentication(
    billing_app: tuple[FastAPI, FakeStripeClient, FakeIdempotencyStore],
) -> None:
    r = client.get("/saas/subscription")
    assert r.status_code == 401


def test_subscription_returns_null_before_checkout(
    billing_app: tuple[FastAPI, FakeStripeClient, FakeIdempotencyStore],
    tenant_id: uuid.UUID,
) -> None:
    r = client.get("/saas/subscription", headers=_auth(tenant_id, Role.VIEWER))
    assert r.status_code == 200
    payload = r.json()
    assert payload["tenant_id"] == str(tenant_id)
    assert payload["subscription_id"] is None
    assert payload["status"] is None


# -- POST /saas/webhook/stripe --------------------------------------------


def _signed_event(
    fake: FakeStripeClient,
    event_id: str,
    event_type: str,
    data: dict[str, object],
) -> tuple[bytes, dict[str, str]]:
    payload = json.dumps({"id": event_id, "type": event_type, "data": {"object": data}}).encode()
    header = fake.sign_webhook(payload, int(time.time()))
    return payload, {"Stripe-Signature": header, "Content-Type": "application/json"}


def test_webhook_rejects_missing_signature(
    billing_app: tuple[FastAPI, FakeStripeClient, FakeIdempotencyStore],
) -> None:
    r = client.post("/saas/webhook/stripe", content=b"{}")
    assert r.status_code == 400
    assert "Stripe-Signature" in r.json()["detail"]


def test_webhook_rejects_bad_signature(
    billing_app: tuple[FastAPI, FakeStripeClient, FakeIdempotencyStore],
) -> None:
    r = client.post(
        "/saas/webhook/stripe",
        content=b'{"id":"evt_bad","type":"x"}',
        headers={"Stripe-Signature": "t=1,v1=deadbeef"},
    )
    assert r.status_code == 400
    assert "signature verification failed" in r.json()["detail"]


def test_webhook_processes_checkout_completed(
    billing_app: tuple[FastAPI, FakeStripeClient, FakeIdempotencyStore],
    tenant_id: uuid.UUID,
) -> None:
    _, fake, store = billing_app
    event_id = "evt_checkout_1"
    payload, headers = _signed_event(
        fake,
        event_id,
        "checkout.session.completed",
        {"subscription": "sub_test_1", "metadata": {"tenant_id": str(tenant_id)}},
    )
    r = client.post("/saas/webhook/stripe", content=payload, headers=headers)
    assert r.status_code == 200
    assert r.json() == {"status": "processed", "event_id": event_id}

    sub_id, status = _read_tenant(tenant_id)
    assert sub_id == "sub_test_1"
    assert status == "active"
    assert store.already_seen(event_id) is True


def test_webhook_duplicate_delivery_does_not_reapply_side_effect(
    billing_app: tuple[FastAPI, FakeStripeClient, FakeIdempotencyStore],
    tenant_id: uuid.UUID,
) -> None:
    """First delivery processes, second returns duplicate, and the
    side effect is not applied twice.

    To prove the second delivery did nothing, the second event carries a
    DIFFERENT subscription ID and status. If idempotency is broken, the
    tenant row would end up with the second event's values; if it works,
    the row still has the first event's values.
    """
    _, fake, _ = billing_app
    event_id = "evt_dup_1"
    payload, headers = _signed_event(
        fake,
        event_id,
        "checkout.session.completed",
        {"subscription": "sub_first", "metadata": {"tenant_id": str(tenant_id)}},
    )
    r1 = client.post("/saas/webhook/stripe", content=payload, headers=headers)
    assert r1.status_code == 200
    assert r1.json()["status"] == "processed"

    # Same event_id, different payload.
    payload2, headers2 = _signed_event(
        fake,
        event_id,
        "checkout.session.completed",
        {"subscription": "sub_second", "metadata": {"tenant_id": str(tenant_id)}},
    )
    r2 = client.post("/saas/webhook/stripe", content=payload2, headers=headers2)
    assert r2.status_code == 200
    assert r2.json()["status"] == "duplicate"

    sub_id, status = _read_tenant(tenant_id)
    assert sub_id == "sub_first", "duplicate delivery should not overwrite the subscription"
    assert status == "active"


def test_webhook_updates_subscription_status(
    billing_app: tuple[FastAPI, FakeStripeClient, FakeIdempotencyStore],
    tenant_id: uuid.UUID,
) -> None:
    """A subscription.updated event updates the tenant's recorded status
    when the subscription ID matches."""
    _, fake, _ = billing_app
    # First, create a subscription on the tenant.
    with admin_session() as s:
        s.execute(
            text(
                "UPDATE tenants SET stripe_subscription_id = :s, "
                "stripe_subscription_status = 'active' WHERE id = :i"
            ),
            {"s": "sub_x", "i": str(tenant_id)},
        )
    # Then deliver a subscription.updated event for that subscription.
    payload, headers = _signed_event(
        fake,
        "evt_sub_update_1",
        "customer.subscription.updated",
        {"id": "sub_x", "status": "past_due"},
    )
    r = client.post("/saas/webhook/stripe", content=payload, headers=headers)
    assert r.status_code == 200
    assert r.json()["status"] == "processed"
    sub_id, status = _read_tenant(tenant_id)
    assert sub_id == "sub_x"
    assert status == "past_due"


def test_webhook_rejects_event_missing_id(
    billing_app: tuple[FastAPI, FakeStripeClient, FakeIdempotencyStore],
) -> None:
    _, fake, _ = billing_app
    payload = json.dumps({"type": "checkout.session.completed"}).encode()
    header = fake.sign_webhook(payload, int(time.time()))
    r = client.post(
        "/saas/webhook/stripe",
        content=payload,
        headers={"Stripe-Signature": header},
    )
    assert r.status_code == 400
    assert "missing id or type" in r.json()["detail"]


def test_webhook_rejects_event_missing_type(
    billing_app: tuple[FastAPI, FakeStripeClient, FakeIdempotencyStore],
) -> None:
    _, fake, _ = billing_app
    payload = json.dumps({"id": "evt_1"}).encode()
    header = fake.sign_webhook(payload, int(time.time()))
    r = client.post(
        "/saas/webhook/stripe",
        content=payload,
        headers={"Stripe-Signature": header},
    )
    assert r.status_code == 400
    assert "missing id or type" in r.json()["detail"]


def test_webhook_unhandled_event_type_still_records(
    billing_app: tuple[FastAPI, FakeStripeClient, FakeIdempotencyStore],
) -> None:
    """An event this MVP does not act on is still recorded in the
    idempotency store, so a retry is deduplicated even though the first
    delivery was a no-op."""
    _, fake, store = billing_app
    payload, headers = _signed_event(
        fake,
        "evt_unknown_1",
        "customer.created",
        {"id": "cus_xyz"},
    )
    r = client.post("/saas/webhook/stripe", content=payload, headers=headers)
    assert r.status_code == 200
    assert r.json()["status"] == "processed"
    assert store.already_seen("evt_unknown_1") is True
