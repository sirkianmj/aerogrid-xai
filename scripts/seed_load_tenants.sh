#!/usr/bin/env bash
# seed_load_tenants.sh — create N tenants and write their bearer tokens
# to /tmp/aerogrid-load-tokens.txt for the load test.
#
# Bypasses the API's rate limiter by hitting Postgres directly for the
# tenant rows, then calls /auth/token once per tenant to obtain a real
# JWT. The tokens are the load test's credentials.
#
# Idempotent: if a tenant already exists, it is left alone; the token
# is re-issued.

set -euo pipefail

N="${1:-100}"
BASE="http://127.0.0.1:8000"
DB_URL="postgresql://aerogrid@127.0.0.1:5432/aerogrid"
TOKEN_FILE="/tmp/aerogrid-load-tokens.txt"
PASSWORD="correct-horse-battery-staple"

echo "seeding ${N} tenants"
: > "${TOKEN_FILE}"

for i in $(seq 1 "${N}"); do
    slug=$(printf "load-%03d" "${i}")
    psql "${DB_URL}" -v ON_ERROR_STOP=1 -v slug="${slug}" -v pw="${PASSWORD}" >/dev/null <<'SQL'
INSERT INTO tenants (slug, display_name, password_hash)
VALUES (:'slug', :'slug', crypt(:'pw', gen_salt('bf', 12)))
ON CONFLICT (slug) DO UPDATE SET password_hash = EXCLUDED.password_hash;
SQL

    token=$(curl -sS -X POST "${BASE}/auth/token" \
        -H "Content-Type: application/json" \
        -d "{\"slug\":\"${slug}\",\"password\":\"${PASSWORD}\"}" \
        | python3 -c "import json,sys; print(json.load(sys.stdin).get('token',''))")

    if [ -z "${token}" ]; then
        echo "  [${i}/${N}] ${slug}: FAILED to obtain token" >&2
        exit 1
    fi
    echo "${token}" >> "${TOKEN_FILE}"
    printf "  [%d/%d] %s\n" "${i}" "${N}" "${slug}"
done

echo "wrote ${N} tokens to ${TOKEN_FILE}"
