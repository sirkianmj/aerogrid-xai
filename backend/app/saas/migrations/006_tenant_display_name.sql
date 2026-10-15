-- Human-readable display name for a tenant.
--
-- Added for the signup flow: a new tenant supplies a display name
-- alongside the slug and password. The slug is the login handle
-- (lowercase, URL-safe, unique); the display name is what appears in
-- the admin panel and in the SaaS UI. It is not unique and not used
-- for authentication.

ALTER TABLE tenants
    ADD COLUMN IF NOT EXISTS display_name VARCHAR(128);

COMMENT ON COLUMN tenants.display_name IS
    'Human-readable tenant name. Not unique, not used for auth.';
