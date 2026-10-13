-- Per-tenant monthly usage counters for quota enforcement.
--
-- A row exists per (tenant_id, metric, period_start). period_start is
-- the first day of the calendar month at 00:00 UTC. count is the
-- cumulative usage in that month for that metric.
--
-- The composite primary key makes the counter update race-safe:
-- concurrent requests increment via
--     INSERT ... ON CONFLICT (tenant_id, metric, period_start)
--     DO UPDATE SET count = quota_usage.count + 1
--     RETURNING count
-- which the PostgreSQL row lock serializes. A read-modify-write in
-- application code would not.
--
-- The table is under RLS for the same reason as missions: read access
-- to a tenant's usage counters must not leak the counters of another
-- tenant. The policy is identical in shape to the missions policy.

CREATE TABLE IF NOT EXISTS quota_usage (
    tenant_id     UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    metric        VARCHAR(32) NOT NULL,
    period_start  DATE NOT NULL,
    count         BIGINT NOT NULL DEFAULT 0,
    PRIMARY KEY (tenant_id, metric, period_start)
);

CREATE INDEX IF NOT EXISTS quota_usage_period_idx
    ON quota_usage (period_start);

ALTER TABLE quota_usage ENABLE ROW LEVEL SECURITY;
ALTER TABLE quota_usage FORCE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS quota_tenant_isolation_policy ON quota_usage;

CREATE POLICY quota_tenant_isolation_policy ON quota_usage
    USING (
        tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid
    )
    WITH CHECK (
        tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid
    );

GRANT SELECT, INSERT, UPDATE, DELETE ON quota_usage TO aerogrid_app;
