-- Multi-tenant SaaS schema with row-level security.
--
-- Two tables: tenants (top-level partition, no RLS) and missions
-- (tenant-scoped, RLS policy keyed on current_setting('app.tenant_id')).
--
-- Every SELECT, UPDATE, and DELETE on the missions table is filtered
-- by PostgreSQL. A query that omits a WHERE tenant_id clause still
-- returns zero rows for the wrong tenant. The policy is FORCED so it
-- applies to the table owner as well; without FORCE, the role that
-- created the table would bypass its own policy.

CREATE EXTENSION IF NOT EXISTS "pgcrypto";

CREATE TABLE IF NOT EXISTS tenants (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    slug          VARCHAR(64) UNIQUE NOT NULL,
    display_name  VARCHAR(256) NOT NULL,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS missions (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id   UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    name        VARCHAR(256) NOT NULL,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS missions_tenant_id_idx ON missions (tenant_id);

-- Enable row-level security and force it on the table owner.
ALTER TABLE missions ENABLE ROW LEVEL SECURITY;
ALTER TABLE missions FORCE ROW LEVEL SECURITY;

-- Drop the policy if it already exists so the migration is idempotent.
DROP POLICY IF EXISTS tenant_isolation_policy ON missions;

-- The policy must handle three states of the app.tenant_id GUC:
--
--   1. never set on this session  -> current_setting(..., true) returns
--      the empty string, not NULL. Casting '' to uuid raises
--      InvalidTextRepresentation.
--   2. set to a valid UUID by tenant_session() -> filtering works.
--   3. explicitly reset to NULL   -> also handled by the same NULLIF.
--
-- NULLIF(current_setting('app.tenant_id', true), '') returns NULL in
-- state 1, and NULL::uuid is NULL. The comparison tenant_id = NULL is
-- NULL, which the policy treats as FALSE, so the row is filtered out
-- rather than causing a cast error.
CREATE POLICY tenant_isolation_policy ON missions
    USING (
        tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid
    )
    WITH CHECK (
        tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid
    );

-- Application role.
--
-- The database was initialised by ``initdb --username=aerogrid``, which
-- makes aerogrid the bootstrap superuser. Superusers bypass row-level
-- security unconditionally: "Superusers and roles with the BYPASSRLS
-- attribute always bypass the row security system when accessing a
-- table" (PostgreSQL documentation, CREATE POLICY). FORCE ROW LEVEL
-- SECURITY does not change that; it only removes the table-owner
-- exemption, not the superuser exemption.
--
-- The tenant_session helper therefore switches to a non-superuser
-- application role for every tenant-scoped query. aerogrid_app has
-- NOSUPERUSER and NOBYPASSRLS (both default for a new role, stated
-- explicitly so the intent is on the record), and only the privileges
-- it needs: SELECT, INSERT, UPDATE, DELETE on missions, and USAGE on
-- the public schema. It has no grant on the tenants table, so the
-- tenant-scoped code path cannot enumerate tenants.
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'aerogrid_app') THEN
        CREATE ROLE aerogrid_app NOLOGIN NOSUPERUSER NOBYPASSRLS;
    END IF;
END
$$;

GRANT USAGE ON SCHEMA public TO aerogrid_app;
GRANT SELECT, INSERT, UPDATE, DELETE ON missions TO aerogrid_app;
GRANT SELECT ON tenants TO aerogrid_app;
