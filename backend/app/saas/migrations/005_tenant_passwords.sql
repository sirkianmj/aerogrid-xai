-- Tenant passwords for the sign-in flow.
--
-- Adds a nullable password_hash column to tenants. NULL means the
-- tenant cannot log in via password; the operator must provision one
-- with scripts/provision_dev_tenant.sh (or the equivalent production
-- provisioning step) before login is possible for that tenant.
--
-- Hashes are produced by pgcrypto's crypt() with a bcrypt salt
-- (gen_salt('bf', 12)). pgcrypto is already installed by migration
-- 001. Password verification also happens inside Postgres, so the
-- plaintext never reaches the Python layer as a hash comparison.
--
-- No index is added: the login lookup is by slug, which already has
-- a UNIQUE index from migration 001.

ALTER TABLE tenants
    ADD COLUMN IF NOT EXISTS password_hash VARCHAR(255);

COMMENT ON COLUMN tenants.password_hash IS
    'bcrypt hash produced by pgcrypto crypt(password, gen_salt(''bf'', 12)). NULL means the tenant cannot log in via password.';
