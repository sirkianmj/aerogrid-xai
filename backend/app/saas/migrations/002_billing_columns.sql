-- Billing columns and idempotency table for Stripe integration.
--
-- The tenants table gains three nullable columns for the Stripe
-- customer ID, subscription ID, and last-known subscription status.
-- None of them is required; a tenant exists before billing begins.
--
-- The stripe_events table is the idempotency store for the webhook
-- handler. Stripe delivers events at least once; the handler must
-- deduplicate on the event ID before performing side effects. The
-- table is not tenant-scoped and not under RLS: webhook delivery is a
-- system-level operation, authenticated by HMAC signature, not by a
-- tenant JWT.

ALTER TABLE tenants
    ADD COLUMN IF NOT EXISTS stripe_customer_id VARCHAR(64),
    ADD COLUMN IF NOT EXISTS stripe_subscription_id VARCHAR(64),
    ADD COLUMN IF NOT EXISTS stripe_subscription_status VARCHAR(32);

CREATE INDEX IF NOT EXISTS tenants_stripe_customer_idx
    ON tenants (stripe_customer_id);

CREATE TABLE IF NOT EXISTS stripe_events (
    event_id     VARCHAR(128) PRIMARY KEY,
    event_type   VARCHAR(128) NOT NULL,
    received_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS stripe_events_received_at_idx
    ON stripe_events (received_at);
