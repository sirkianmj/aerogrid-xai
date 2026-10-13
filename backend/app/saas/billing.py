"""Stripe billing integration.

The SaaS layer treats Stripe as an external dependency behind a small
protocol. Three implementations satisfy the protocol:

  - LiveStripeClient   wraps stripe.StripeClient and calls the real API
  - FakeStripeClient   in-memory double used by tests
  - (a test-scope one-off built inside individual tests, if needed)

The protocol exposes only the operations this codebase performs. It is
deliberately small: three subscription/customer methods, one checkout
method, one webhook verifier. Nothing else from the Stripe SDK is
reachable from application code.

Configuration
-------------

Read from the environment:

    AEROGRID_STRIPE_SECRET_KEY       Stripe API secret key (sk_...)
    AEROGRID_STRIPE_WEBHOOK_SECRET   Stripe webhook signing secret (whsec_...)
    AEROGRID_STRIPE_PRICE_ID         Stripe price ID for the SaaS plan

In AEROGRID_ENV=development the three may be unset and a live client
will refuse to be constructed. Tests use the fake client, which never
reads them. Outside development all three must be set; the config
raises RuntimeError if any is missing, matching the pattern in
app.saas.auth for the JWT signing secret.

Real network calls are not exercised by the test suite. The tests
cover the config, the protocol, the fake client including its HMAC
verification, and the live client's construction. The live client's
API calls are validated manually against a Stripe test-mode account
before any deployment; that step is documented in the s8-5 acceptance
notes, not automated.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Protocol, cast, runtime_checkable

import stripe


@dataclass(frozen=True)
class StripeConfig:
    """Resolved Stripe configuration for the process.

    Attributes:
        secret_key: Stripe API secret key, e.g. sk_test_...
        webhook_secret: Stripe webhook signing secret, e.g. whsec_...
        price_id: The Stripe price the SaaS subscription uses.
        livemode: True when the secret key starts with sk_live_.
    """

    secret_key: str
    webhook_secret: str
    price_id: str

    @property
    def livemode(self) -> bool:
        return self.secret_key.startswith("sk_live_")


def stripe_config() -> StripeConfig:
    """Return the process Stripe configuration.

    Raises:
        RuntimeError if the environment is not 'development' and any of
            the three required variables is unset.
    """
    env = os.environ.get("AEROGRID_ENV", "development")
    secret_key = os.environ.get("AEROGRID_STRIPE_SECRET_KEY")
    webhook_secret = os.environ.get("AEROGRID_STRIPE_WEBHOOK_SECRET")
    price_id = os.environ.get("AEROGRID_STRIPE_PRICE_ID")

    if env == "development":
        # In development the caller may pass placeholder values, or may
        # not use the live client at all. The empty strings here are not
        # secrets; they exist so a dev shell can construct the config
        # without a real Stripe account.
        return StripeConfig(
            secret_key=secret_key or "",
            webhook_secret=webhook_secret or "",
            price_id=price_id or "",
        )

    missing = [
        name
        for name, value in (
            ("AEROGRID_STRIPE_SECRET_KEY", secret_key),
            ("AEROGRID_STRIPE_WEBHOOK_SECRET", webhook_secret),
            ("AEROGRID_STRIPE_PRICE_ID", price_id),
        )
        if not value
    ]
    if missing:
        raise RuntimeError("Stripe configuration is incomplete; missing: " + ", ".join(missing))

    assert secret_key is not None
    assert webhook_secret is not None
    assert price_id is not None
    return StripeConfig(
        secret_key=secret_key,
        webhook_secret=webhook_secret,
        price_id=price_id,
    )


@dataclass(frozen=True)
class CustomerInfo:
    id: str
    email: str


@dataclass(frozen=True)
class CheckoutSession:
    id: str
    url: str


@dataclass(frozen=True)
class SubscriptionInfo:
    id: str
    status: str
    current_period_end_unix: int


@runtime_checkable
class StripeClient(Protocol):
    """The subset of Stripe operations this codebase uses.

    Every method is documented with the shape of the object it must
    return. Both LiveStripeClient and FakeStripeClient satisfy the
    protocol; the type checker enforces it at the call site.
    """

    def create_customer(self, *, email: str, tenant_id: str) -> CustomerInfo:
        """Create a Stripe customer for a tenant."""
        ...

    def create_checkout_session(
        self,
        *,
        customer_id: str,
        price_id: str,
        success_url: str,
        cancel_url: str,
        tenant_id: str,
    ) -> CheckoutSession:
        """Create a Stripe Checkout session for a subscription purchase."""
        ...

    def retrieve_subscription(self, subscription_id: str) -> SubscriptionInfo:
        """Return the current state of one subscription."""
        ...

    def cancel_subscription(self, subscription_id: str) -> SubscriptionInfo:
        """Cancel a subscription immediately."""
        ...

    def verify_webhook(self, payload: bytes, sig_header: str) -> dict[str, object]:
        """Verify a Stripe webhook signature and return the parsed event.

        Raises:
            stripe.error.SignatureVerificationError if the signature is
            invalid.
        """
        ...


def _current_period_end_unix(subscription: object) -> int:
    """Return the subscription's current period end as a Unix timestamp.

    Stripe SDK 16 exposes current_period_end on the subscription's
    items rather than on the subscription itself. Older shapes expose it
    at the top level. This helper tries the top level first, then falls
    back to the first item.
    """
    top = getattr(subscription, "current_period_end", None)
    if isinstance(top, int):
        return top
    items = getattr(subscription, "items", None)
    data = getattr(items, "data", None)
    if isinstance(data, list) and data:
        first = data[0]
        value = getattr(first, "current_period_end", None)
        if isinstance(value, int):
            return value
    raise RuntimeError(
        "Stripe subscription is missing current_period_end in both "
        "the top-level and per-item location"
    )


class LiveStripeClient:
    """StripeClient implementation backed by the real Stripe API.

    The constructor refuses to build if the config is incomplete, so a
    misconfigured process fails at startup rather than on the first
    request.
    """

    def __init__(self, config: StripeConfig | None = None) -> None:
        self._config = config if config is not None else stripe_config()
        if not self._config.secret_key:
            raise RuntimeError(
                "LiveStripeClient requires AEROGRID_STRIPE_SECRET_KEY; "
                "use FakeStripeClient in tests"
            )
        if not self._config.webhook_secret:
            raise RuntimeError("LiveStripeClient requires AEROGRID_STRIPE_WEBHOOK_SECRET")
        self._client = stripe.StripeClient(api_key=self._config.secret_key)

    @property
    def config(self) -> StripeConfig:
        return self._config

    def create_customer(self, *, email: str, tenant_id: str) -> CustomerInfo:
        raw = self._client.customers.create(
            params={"email": email, "metadata": {"tenant_id": tenant_id}}
        )
        return CustomerInfo(id=str(raw.id), email=email)

    def create_checkout_session(
        self,
        *,
        customer_id: str,
        price_id: str,
        success_url: str,
        cancel_url: str,
        tenant_id: str,
    ) -> CheckoutSession:
        raw = self._client.checkout.sessions.create(
            params={
                "mode": "subscription",
                "customer": customer_id,
                "line_items": [{"price": price_id, "quantity": 1}],
                "success_url": success_url,
                "cancel_url": cancel_url,
                "metadata": {"tenant_id": tenant_id},
            }
        )
        url = raw.url
        if url is None:
            raise RuntimeError("Stripe returned a checkout session without a URL")
        return CheckoutSession(id=str(raw.id), url=str(url))

    def retrieve_subscription(self, subscription_id: str) -> SubscriptionInfo:
        raw = self._client.subscriptions.retrieve(subscription_id)
        return SubscriptionInfo(
            id=str(raw.id),
            status=str(raw.status),
            current_period_end_unix=_current_period_end_unix(raw),
        )

    def cancel_subscription(self, subscription_id: str) -> SubscriptionInfo:
        raw = self._client.subscriptions.cancel(subscription_id)
        return SubscriptionInfo(
            id=str(raw.id),
            status=str(raw.status),
            current_period_end_unix=_current_period_end_unix(raw),
        )

    def verify_webhook(self, payload: bytes, sig_header: str) -> dict[str, object]:
        event = self._client.construct_event(
            payload,
            sig_header,
            self._config.webhook_secret,
        )
        # StripeObject supports the dict protocol at runtime (it
        # implements __iter__ and __getitem__), but the type stubs that
        # ship with stripe 16 do not declare it as a Mapping. cast() is
        # the correct tool here: it is a no-op at runtime and tells the
        # type checker that the value conforms to a shape the stubs do
        # not describe.
        raw_dict = cast("dict[str, object]", event)
        return dict(raw_dict)
