-- Revoke SELECT on tenants from aerogrid_app.
--
-- Finding F-1 in docs/ISOLATION_AUDIT.md: the tenants table is not
-- under RLS, and 001 granted SELECT on it to aerogrid_app. A session
-- that issued SET LOCAL ROLE aerogrid_app and then queried tenants
-- would return every tenant row. No current code path does this --
-- get_tenant_plan, billing_routes.create_checkout_session, and
-- billing_routes.get_subscription all use admin_session, which runs as
-- the superuser -- but the grant is unnecessary for a role whose
-- purpose is tenant-scoped work.
--
-- Revoking is safe. No test and no production code path uses
-- tenant_session to read from tenants. After this migration, a tenant
-- session that queries tenants fails at the SQL layer with
-- InsufficientPrivilege, which is the correct failure mode: loud, not
-- silent.

REVOKE SELECT ON tenants FROM aerogrid_app;
