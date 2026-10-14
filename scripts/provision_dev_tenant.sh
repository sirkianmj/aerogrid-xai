#!/usr/bin/env bash
# scripts/provision_dev_tenant.sh
#
# Creates or updates a tenant with a bcrypt-hashed password. For local
# development and integration tests. Not for production use.
#
# Usage:
#   scripts/provision_dev_tenant.sh <slug> <password> [display-name]
#
# Example:
#   scripts/provision_dev_tenant.sh acme 'correct horse battery staple' 'Acme Corp'
#
# Runs against the local PostgreSQL started by scripts/start_services.sh.
#
# The password is passed to psql as a psql variable (-v password=...),
# never as a shell argument to psql directly, and the SQL body is fed
# over stdin. It is still visible in the shell's own argument list at
# invocation time; for real deployments use the production provisioning
# path, not this script.

set -euo pipefail

SLUG="${1:?slug required}"
PASSWORD="${2:?password required}"
DISPLAY="${3:-Demo Tenant}"

psql -U aerogrid -p 5432 -d aerogrid \
    -v ON_ERROR_STOP=1 \
    -v slug="${SLUG}" \
    -v display="${DISPLAY}" \
    -v password="${PASSWORD}" \
    <<'SQL'
INSERT INTO tenants (slug, display_name, password_hash)
VALUES (:'slug', :'display', crypt(:'password', gen_salt('bf', 12)))
ON CONFLICT (slug) DO UPDATE
    SET password_hash = EXCLUDED.password_hash,
        display_name  = EXCLUDED.display_name;
SQL

echo "provisioned tenant: slug=${SLUG}  display_name=${DISPLAY}"
