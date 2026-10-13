"""Tests for the Stripe billing integration.

These tests exercise config rigor, the fake client, and the HMAC
signature round-trip. They never make a network call. A live-client
API call is validated manually against a Stripe test-mode account
before any deployment; that step is not automated here.
"""

from __future__ import annotations

import json
import time

import pytest
import stripe

from app.saas.billing import (
    CheckoutSession,
    CustomerInfo,
    LiveStripeClient,
    StripeClient,
    StripeConfig,
    stripe_config,
)
from app.saas.fake_stripe import DEFAULT_WEBHOOK_SECRET, FakeStripeClient

# -- stripe_config ---------------------------------------------------------


def test_config_development_returns_placeholders(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AEROGRID_ENV", "development")
    monkeypatch.delenv("AEROGRID_STRIPE_SECRET_KEY", raising=False)
    monkeypatch.delenv("AEROGRID_STRIPE_WEBHOOK_SECRET", raising=False)
    monkeypatch.delenv("AEROGRID_STRIPE_PRICE_ID", raising=False)
    cfg = stripe_config()
    assert cfg.secret_key == ""
    assert cfg.webhook_secret == ""
    assert cfg.price_id == ""
    assert cfg.livemode is False


def test_config_development_picks_up_env_overrides(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AEROGRID_ENV", "development")
    monkeypatch.setenv("AEROGRID_STRIPE_SECRET_KEY", "sk_test_abc")
    monkeypatch.setenv("AEROGRID_STRIPE_WEBHOOK_SECRET", "whsec_test_abc")
    monkeypatch.setenv("AEROGRID_STRIPE_PRICE_ID", "price_test_abc")
    cfg = stripe_config()
    assert cfg.secret_key == "sk_test_abc"
    assert cfg.webhook_secret == "whsec_test_abc"
    assert cfg.price_id == "price_test_abc"
    assert cfg.livemode is False


def test_config_rejects_incomplete_production(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AEROGRID_ENV", "production")
    monkeypatch.setenv("AEROGRID_STRIPE_SECRET_KEY", "sk_live_abc")
    monkeypatch.delenv("AEROGRID_STRIPE_WEBHOOK_SECRET", raising=False)
    monkeypatch.delenv("AEROGRID_STRIPE_PRICE_ID", raising=False)
    with pytest.raises(RuntimeError, match="AEROGRID_STRIPE_WEBHOOK_SECRET"):
        stripe_config()


def test_config_livemode_flag_true_for_live_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AEROGRID_ENV", "production")
    monkeypatch.setenv("AEROGRID_STRIPE_SECRET_KEY", "sk_live_abc")
    monkeypatch.setenv("AEROGRID_STRIPE_WEBHOOK_SECRET", "whsec_live_abc")
    monkeypatch.setenv("AEROGRID_STRIPE_PRICE_ID", "price_live_abc")
    cfg = stripe_config()
    assert cfg.livemode is True


# -- LiveStripeClient construction ----------------------------------------


def test_live_client_refuses_empty_secret() -> None:
    cfg = StripeConfig(secret_key="", webhook_secret="whsec_x", price_id="price_x")
    with pytest.raises(RuntimeError, match="AEROGRID_STRIPE_SECRET_KEY"):
        LiveStripeClient(cfg)


def test_live_client_refuses_empty_webhook_secret() -> None:
    cfg = StripeConfig(secret_key="sk_test_x", webhook_secret="", price_id="price_x")
    with pytest.raises(RuntimeError, match="AEROGRID_STRIPE_WEBHOOK_SECRET"):
        LiveStripeClient(cfg)


def test_live_client_constructs_with_test_key() -> None:
    """Constructing the live client only initializes the SDK; no network
    call is made until a method is called. This test asserts that the
    wrapper holds the configured client.
    """
    cfg = StripeConfig(
        secret_key="sk_test_placeholder",
        webhook_secret="whsec_test_placeholder",
        price_id="price_test_placeholder",
    )
    client = LiveStripeClient(cfg)
    assert isinstance(client, StripeClient)
    assert client.config is cfg


# -- FakeStripeClient ------------------------------------------------------


def test_fake_satisfies_protocol() -> None:
    fake = FakeStripeClient()
    assert isinstance(fake, StripeClient)


def test_fake_create_customer_returns_id() -> None:
    fake = FakeStripeClient()
    info = fake.create_customer(email="a@example.com", tenant_id="t-1")
    assert isinstance(info, CustomerInfo)
    assert info.id.startswith("cus_")
    assert info.email == "a@example.com"
    assert info.id in fake.customers


def test_fake_checkout_session_references_existing_customer() -> None:
    fake = FakeStripeClient()
    cust = fake.create_customer(email="a@example.com", tenant_id="t-1")
    session = fake.create_checkout_session(
        customer_id=cust.id,
        price_id="price_x",
        success_url="https://example.com/ok",
        cancel_url="https://example.com/no",
        tenant_id="t-1",
    )
    assert isinstance(session, CheckoutSession)
    assert session.url.startswith("https://checkout.stripe.test/")
    assert session.id in fake.checkout_sessions


def test_fake_checkout_rejects_unknown_customer() -> None:
    fake = FakeStripeClient()
    with pytest.raises(ValueError, match="unknown customer_id"):
        fake.create_checkout_session(
            customer_id="cus_does_not_exist",
            price_id="price_x",
            success_url="https://example.com/ok",
            cancel_url="https://example.com/no",
            tenant_id="t-1",
        )


def test_fake_add_and_retrieve_subscription() -> None:
    fake = FakeStripeClient()
    cust = fake.create_customer(email="a@example.com", tenant_id="t-1")
    sub = fake.add_subscription(customer_id=cust.id, status="active")
    info = fake.retrieve_subscription(sub.id)
    assert info.status == "active"
    assert info.id == sub.id


def test_fake_cancel_subscription_changes_status() -> None:
    fake = FakeStripeClient()
    cust = fake.create_customer(email="a@example.com", tenant_id="t-1")
    sub = fake.add_subscription(customer_id=cust.id, status="active")
    canceled = fake.cancel_subscription(sub.id)
    assert canceled.status == "canceled"
    assert fake.retrieve_subscription(sub.id).status == "canceled"


def test_fake_retrieve_unknown_subscription_raises() -> None:
    fake = FakeStripeClient()
    with pytest.raises(ValueError, match="unknown subscription_id"):
        fake.retrieve_subscription("sub_does_not_exist")


# -- Webhook signature round trip -----------------------------------------


def test_fake_signs_and_verifies_webhook() -> None:
    fake = FakeStripeClient()
    payload = json.dumps({"type": "checkout.session.completed", "id": "evt_1"}).encode()
    ts = int(time.time())
    header = fake.sign_webhook(payload, ts)
    event = fake.verify_webhook(payload, header)
    assert event["type"] == "checkout.session.completed"
    assert event["id"] == "evt_1"


def test_fake_verify_rejects_bad_signature() -> None:
    fake = FakeStripeClient()
    payload = b'{"type":"x"}'
    bad_header = "t=1,v1=deadbeef"
    with pytest.raises(stripe.error.SignatureVerificationError):
        fake.verify_webhook(payload, bad_header)


def test_fake_verify_rejects_missing_fields() -> None:
    fake = FakeStripeClient()
    with pytest.raises(stripe.error.SignatureVerificationError, match="missing t or v1"):
        fake.verify_webhook(b"x", "v1=abc")


def test_fake_default_webhook_secret_is_documented_value() -> None:
    assert DEFAULT_WEBHOOK_SECRET.startswith("whsec_test_")
