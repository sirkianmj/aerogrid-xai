"""In-memory StripeClient double for tests.

Satisfies the StripeClient protocol without touching the network. The
webhook verifier computes the same HMAC-SHA256 signature that Stripe
computes (RFC: the `t` and `v1` fields of the Stripe-Signature header),
so a test that constructs a valid header exercises the real
verification code path in the live client's counterpart.

No network access. No real Stripe account. No placeholder keys with
which an SDK might reach out.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import uuid
from dataclasses import dataclass, field

import stripe

from app.saas.billing import CheckoutSession, CustomerInfo, SubscriptionInfo


def _sig_error(message: str, sig_header: str) -> Exception:
    """Return a stripe SignatureVerificationError.

    The Stripe SDK's SignatureVerificationError is declared without
    argument types in the stubs that ship with version 16, so mypy
    raises no-untyped-call on the constructor. The ignore is scoped to
    that single call; the return type is annotated so callers see a
    typed Exception.
    """
    return stripe.error.SignatureVerificationError(  # type: ignore[no-untyped-call]
        message, sig_header
    )


DEFAULT_WEBHOOK_SECRET = "whsec_test_webhook_secret_for_fake_stripe_client"


@dataclass
class _Customer:
    id: str
    email: str
    tenant_id: str


@dataclass
class _Subscription:
    id: str
    customer_id: str
    status: str
    current_period_end_unix: int


@dataclass
class FakeStripeClient:
    """In-memory implementation of StripeClient for tests.

    Attributes:
        webhook_secret: Used to compute signatures in tests that exercise
            verify_webhook. Set to a documented test value.
    """

    webhook_secret: str = DEFAULT_WEBHOOK_SECRET
    customers: dict[str, _Customer] = field(default_factory=dict)
    subscriptions: dict[str, _Subscription] = field(default_factory=dict)
    checkout_sessions: dict[str, dict[str, str]] = field(default_factory=dict)
    _next_period_end: int = 1_800_000_000

    # --- customers ---

    def create_customer(self, *, email: str, tenant_id: str) -> CustomerInfo:
        cid = f"cus_{uuid.uuid4().hex[:16]}"
        self.customers[cid] = _Customer(id=cid, email=email, tenant_id=tenant_id)
        return CustomerInfo(id=cid, email=email)

    # --- checkout ---

    def create_checkout_session(
        self,
        *,
        customer_id: str,
        price_id: str,
        success_url: str,
        cancel_url: str,
        tenant_id: str,
    ) -> CheckoutSession:
        if customer_id not in self.customers:
            raise ValueError(f"unknown customer_id: {customer_id}")
        sid = f"cs_test_{uuid.uuid4().hex[:16]}"
        url = f"https://checkout.stripe.test/pay/{sid}"
        self.checkout_sessions[sid] = {
            "customer_id": customer_id,
            "price_id": price_id,
            "success_url": success_url,
            "cancel_url": cancel_url,
            "tenant_id": tenant_id,
        }
        return CheckoutSession(id=sid, url=url)

    # --- subscriptions ---

    def retrieve_subscription(self, subscription_id: str) -> SubscriptionInfo:
        sub = self.subscriptions.get(subscription_id)
        if sub is None:
            raise ValueError(f"unknown subscription_id: {subscription_id}")
        return SubscriptionInfo(
            id=sub.id,
            status=sub.status,
            current_period_end_unix=sub.current_period_end_unix,
        )

    def cancel_subscription(self, subscription_id: str) -> SubscriptionInfo:
        sub = self.subscriptions.get(subscription_id)
        if sub is None:
            raise ValueError(f"unknown subscription_id: {subscription_id}")
        sub.status = "canceled"
        return SubscriptionInfo(
            id=sub.id,
            status=sub.status,
            current_period_end_unix=sub.current_period_end_unix,
        )

    # --- test helpers (not part of the protocol) ---

    def add_subscription(
        self,
        *,
        customer_id: str,
        status: str = "active",
        current_period_end_unix: int | None = None,
    ) -> SubscriptionInfo:
        """Test helper: create a subscription in the fake store."""
        if customer_id not in self.customers:
            raise ValueError(f"unknown customer_id: {customer_id}")
        sid = f"sub_{uuid.uuid4().hex[:16]}"
        sub = _Subscription(
            id=sid,
            customer_id=customer_id,
            status=status,
            current_period_end_unix=current_period_end_unix
            if current_period_end_unix is not None
            else self._next_period_end,
        )
        self.subscriptions[sid] = sub
        return SubscriptionInfo(
            id=sid,
            status=sub.status,
            current_period_end_unix=sub.current_period_end_unix,
        )

    def sign_webhook(self, payload: bytes, timestamp: int) -> str:
        """Compute the Stripe-Signature header for a payload and timestamp.

        The header format is

            t=<unix timestamp>,v1=<hex HMAC-SHA256>

        where the HMAC is computed over

            "<timestamp>.<payload>"

        with the webhook secret as the key. This matches the format the
        Stripe SDK accepts in construct_event.
        """
        signed = f"{timestamp}.".encode() + payload
        mac = hmac.new(self.webhook_secret.encode(), signed, hashlib.sha256)
        return f"t={timestamp},v1={mac.hexdigest()}"

    def verify_webhook(self, payload: bytes, sig_header: str) -> dict[str, object]:
        """Verify a header produced by sign_webhook and return the event.

        Raises:
            stripe.error.SignatureVerificationError if the signature
            does not match.
        """
        parts = dict(item.split("=", 1) for item in sig_header.split(","))
        ts = parts.get("t")
        v1 = parts.get("v1")
        if ts is None or v1 is None:
            raise _sig_error("missing t or v1 in signature header", sig_header)
        expected = self.sign_webhook(payload, int(ts))
        expected_v1 = dict(item.split("=", 1) for item in expected.split(","))["v1"]
        if not hmac.compare_digest(v1, expected_v1):
            raise _sig_error("signature mismatch", sig_header)
        parsed = json.loads(payload.decode())
        if not isinstance(parsed, dict):
            raise _sig_error("payload is not a JSON object", sig_header)
        return {str(k): v for k, v in parsed.items()}
