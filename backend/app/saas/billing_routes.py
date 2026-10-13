"""HTTP routes for Stripe billing.

Three routes under /saas:

  POST /saas/checkout-session    authenticated tenant, creates a Stripe
                                 Checkout session for the SaaS plan
  GET  /saas/subscription        authenticated tenant, returns the
                                 current subscription state
  POST /saas/webhook/stripe      unauthenticated by JWT, authenticated
                                 by Stripe HMAC signature; processes
                                 subscription lifecycle events

Authentication model
--------------------

The two authenticated routes require a tenant JWT (via
app.saas.auth.require_role). The webhook route does not accept a JWT:
it is called by Stripe, and its caller is authenticated by the HMAC
signature over the raw request body. The signature check is performed
by StripeClient.verify_webhook, which uses the webhook secret from
app.saas.billing.stripe_config.

Idempotency
-----------

The webhook route records each event ID in an IdempotencyStore before
performing side effects. A duplicate delivery returns 200 with
status="duplicate" and no side effect. The production store is
PostgreSQL-backed; the tests use an in-memory double.

Client injection
----------------

The Stripe client and the idempotency store are resolved through
FastAPI dependencies that read from app.state. The application startup
path sets app.state.stripe_client to LiveStripeClient when the config
is complete, and leaves it unset otherwise (the routes return 503).
Tests set app.state.stripe_client to FakeStripeClient and
app.state.idempotency_store to FakeIdempotencyStore.
"""

from __future__ import annotations

from typing import Any

import stripe
from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel
from sqlalchemy import text

from app.saas.auth import Role, TenantContext, require_role
from app.saas.billing import StripeClient, stripe_config
from app.saas.db import admin_session
from app.saas.idempotency import IdempotencyStore, PostgresIdempotencyStore

router = APIRouter(prefix="/saas", tags=["saas-billing"])


def get_stripe_client(request: Request) -> StripeClient:
    """FastAPI dependency: return the app-wide Stripe client.

    The client is created lazily by the startup path and stored on
    app.state. If the config is incomplete the attribute is unset and
    the route returns 503 rather than 500.
    """
    client: StripeClient | None = getattr(request.app.state, "stripe_client", None)
    if client is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Stripe client not configured",
        )
    return client


def get_idempotency_store(request: Request) -> IdempotencyStore:
    """FastAPI dependency: return the app-wide idempotency store.

    Lazily instantiated as a PostgresIdempotencyStore on first use.
    Tests override by setting app.state.idempotency_store.
    """
    store: IdempotencyStore | None = getattr(request.app.state, "idempotency_store", None)
    if store is None:
        store = PostgresIdempotencyStore()
        request.app.state.idempotency_store = store
    return store


# --- routes ---------------------------------------------------------------


class CheckoutSessionResponse(BaseModel):
    checkout_url: str
    session_id: str


@router.post("/checkout-session", response_model=CheckoutSessionResponse)
async def create_checkout_session(
    ctx: TenantContext = Depends(require_role(Role.ADMIN)),
    client: StripeClient = Depends(get_stripe_client),
) -> CheckoutSessionResponse:
    """Create a Stripe Checkout session for the caller's tenant.

    Requires admin role. If the tenant has no Stripe customer yet, one
    is created on demand and recorded on the tenants row. The price ID
    comes from stripe_config(); an empty price ID is a server-side
    configuration error and returns 503.
    """
    with admin_session() as s:
        row = s.execute(
            text("SELECT slug, display_name, stripe_customer_id FROM tenants WHERE id = :id"),
            {"id": str(ctx.tenant_id)},
        ).first()
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"tenant {ctx.tenant_id} not found",
        )
    slug, display_name, customer_id = row[0], row[1], row[2]

    if customer_id is None:
        # Create a customer. The email address is a placeholder; a real
        # deployment would collect it during signup and store it on the
        # tenants row.
        customer = client.create_customer(
            email=f"{slug}@tenants.aerogrid-xai.example",
            tenant_id=str(ctx.tenant_id),
        )
        customer_id = customer.id
        with admin_session() as s:
            s.execute(
                text("UPDATE tenants SET stripe_customer_id = :c WHERE id = :id"),
                {"c": customer_id, "id": str(ctx.tenant_id)},
            )

    cfg = stripe_config()
    if not cfg.price_id:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="AEROGRID_STRIPE_PRICE_ID is not configured",
        )

    session = client.create_checkout_session(
        customer_id=str(customer_id),
        price_id=cfg.price_id,
        success_url="https://aerogrid-xai.example/billing/success",
        cancel_url="https://aerogrid-xai.example/billing/cancel",
        tenant_id=str(ctx.tenant_id),
    )
    _ = display_name  # retained for a future richer response
    return CheckoutSessionResponse(
        checkout_url=session.url,
        session_id=session.id,
    )


class SubscriptionResponse(BaseModel):
    tenant_id: str
    subscription_id: str | None
    status: str | None


@router.get("/subscription", response_model=SubscriptionResponse)
async def get_subscription(
    ctx: TenantContext = Depends(require_role(Role.VIEWER)),
) -> SubscriptionResponse:
    """Return the caller tenant's subscription ID and last-known status.

    The subscription ID and status are updated by the webhook handler
    when Stripe reports a lifecycle event. This route does not call
    Stripe; it reads what the webhook has already recorded.
    """
    with admin_session() as s:
        row = s.execute(
            text(
                "SELECT stripe_subscription_id, stripe_subscription_status "
                "FROM tenants WHERE id = :id"
            ),
            {"id": str(ctx.tenant_id)},
        ).first()
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"tenant {ctx.tenant_id} not found",
        )
    return SubscriptionResponse(
        tenant_id=str(ctx.tenant_id),
        subscription_id=row[0],
        status=row[1],
    )


class WebhookResponse(BaseModel):
    status: str
    event_id: str


def _apply_event(event: dict[str, Any], event_type: str) -> None:
    """Apply the side effect of a verified, not-yet-seen event.

    Handles the two lifecycle events this MVP tracks:

      checkout.session.completed   the customer completed checkout;
                                    record the subscription ID on the
                                    tenant named in the event metadata
      customer.subscription.updated
      customer.subscription.deleted
                                    update the tenant's recorded
                                    subscription status
    """
    if event_type == "checkout.session.completed":
        data = event.get("data")
        if not isinstance(data, dict):
            return
        obj = data.get("object")
        if not isinstance(obj, dict):
            return
        metadata = obj.get("metadata")
        tenant_id = metadata.get("tenant_id") if isinstance(metadata, dict) else None
        subscription_id = obj.get("subscription")
        if not isinstance(tenant_id, str) or not isinstance(subscription_id, str):
            return
        with admin_session() as s:
            s.execute(
                text(
                    "UPDATE tenants SET stripe_subscription_id = :sub, "
                    "stripe_subscription_status = 'active' WHERE id = :id"
                ),
                {"sub": subscription_id, "id": tenant_id},
            )
    elif event_type in (
        "customer.subscription.updated",
        "customer.subscription.deleted",
    ):
        data = event.get("data")
        if not isinstance(data, dict):
            return
        obj = data.get("object")
        if not isinstance(obj, dict):
            return
        subscription_id = obj.get("id")
        new_status = obj.get("status")
        if not isinstance(subscription_id, str) or not isinstance(new_status, str):
            return
        with admin_session() as s:
            s.execute(
                text(
                    "UPDATE tenants SET stripe_subscription_status = :st "
                    "WHERE stripe_subscription_id = :sub"
                ),
                {"st": new_status, "sub": subscription_id},
            )


@router.post("/webhook/stripe", response_model=WebhookResponse)
async def stripe_webhook(
    request: Request,
    client: StripeClient = Depends(get_stripe_client),
    store: IdempotencyStore = Depends(get_idempotency_store),
) -> WebhookResponse:
    """Receive and process a Stripe webhook event.

    Authenticated by the Stripe-Signature header, not by JWT. The body
    is read as raw bytes because the signature is computed over the raw
    payload.

    Returns 200 with status="processed" the first time an event is seen,
    and 200 with status="duplicate" on any subsequent delivery of the
    same event ID. Returns 400 for a missing header, a bad signature, or
    a payload that does not parse to a JSON object with id and type.
    """
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature")
    if not sig_header:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="missing Stripe-Signature header",
        )

    try:
        event = client.verify_webhook(payload, sig_header)
    except stripe.error.SignatureVerificationError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"signature verification failed: {exc}",
        ) from exc

    event_id = event.get("id")
    event_type = event.get("type")
    if not isinstance(event_id, str) or not isinstance(event_type, str):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="event is missing id or type",
        )

    if store.already_seen(event_id):
        return WebhookResponse(status="duplicate", event_id=event_id)

    store.record(event_id, event_type)
    _apply_event(event, event_type)
    return WebhookResponse(status="processed", event_id=event_id)
