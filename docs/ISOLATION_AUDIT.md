# Isolation Audit — AeroGrid-XAI Multi-Tenant Database Layer

**Audit date:** 2026-10-13
**Repository state:** `main` at commit `b9be78b` (PR #76)
**Sprint task:** s8-9 (Scientific gate: isolation at the database level)
**Related tasks:** s8-3 (RLS, PR #71), s8-6 (quota, PR #75)
**Deliverable:** this document; migration `004` below.

## 1. Claim under audit

Tenant isolation in the AeroGrid-XAI SaaS backend is enforced by the
PostgreSQL database, not by application-layer WHERE clauses. A bug in a
FastAPI handler that omits `WHERE tenant_id = ...` cannot leak another
tenant's data, because the database filters the rows before the handler
sees them.

## 2. Scope

Tables audited:

    missions         tenant-scoped data (RLS is expected)
    quota_usage      tenant-scoped data (RLS is expected)
    tenants          top-level partition (RLS not expected)
    stripe_events    system-level idempotency store (RLS not expected)

Roles audited:

    aerogrid         bootstrap superuser (bypasses RLS, by design)
    aerogrid_app     application role used by tenant-scoped sessions

## 3. Method

Three sources of evidence:

1. Live catalogue queries against the running PostgreSQL 16 instance
   (sections 4.1 through 4.5).
2. A read of `backend/app/saas/db.py` and the three migration files.
3. The existing RLS test suite in `backend/tests/test_rls_isolation.py`
   (8 tests) plus one new test added by this audit PR.

## 4. Evidence

### 4.1 RLS flags on each table

    missions       relrowsecurity=t  relforcerowsecurity=t  owner=aerogrid
    quota_usage    relrowsecurity=t  relforcerowsecurity=t  owner=aerogrid
    tenants        relrowsecurity=f  relforcerowsecurity=f  owner=aerogrid
    stripe_events  relrowsecurity=f  relforcerowsecurity=f  owner=aerogrid

`relforcerowsecurity=t` is stronger than `ENABLE` alone. Without FORCE,
the table owner would bypass its own policy; with FORCE, only the
superuser bypass applies.

### 4.2 Policies

    missions      tenant_isolation_policy        PERMISSIVE  ALL  {public}
    quota_usage   quota_tenant_isolation_policy  PERMISSIVE  ALL  {public}

Both policies carry the identical predicate in `USING` and `WITH CHECK`:

    tenant_id = (NULLIF(current_setting('app.tenant_id', true), ''))::uuid

The `NULLIF(..., '')` guard handles the empty-string GUC that an unset
`app.tenant_id` returns on this PostgreSQL version. Without it, `''::uuid`
would raise `InvalidTextRepresentation`.

### 4.3 Role attributes

    aerogrid       rolsuper=t  rolinherit=t  rolcreaterole=t
                   rolcreatedb=t  rolcanlogin=t  rolbypassrls=t

    aerogrid_app   rolsuper=f  rolinherit=t  rolcreaterole=f
                   rolcreatedb=f  rolcanlogin=f  rolbypassrls=f

`aerogrid_app` cannot log in directly (`rolcanlogin=f`). It is reachable
only via `SET LOCAL ROLE aerogrid_app` from a session already
authenticated as the superuser. It cannot bypass RLS.

### 4.4 Grants on tenant-scoped tables

    missions       aerogrid_app:  SELECT, INSERT, UPDATE, DELETE
    quota_usage    aerogrid_app:  SELECT, INSERT, UPDATE, DELETE
    tenants        aerogrid_app:  SELECT                          [F-1]
    stripe_events  aerogrid_app:  (none)

`stripe_events` is deliberately unreachable from a tenant session: it is
a system-level store, populated only by the webhook handler, which runs
under `admin_session`.

### 4.5 Default session

    current_user  = aerogrid
    session_user  = aerogrid
    app.tenant_id = (empty string)

The psql default session is the superuser with no tenant context. This
is the safe baseline: `SET LOCAL ROLE aerogrid_app` without a subsequent
`set_config` yields the "unset GUC" state, which the policy maps to
`NULL` and therefore to zero visible rows.

## 5. How tenant_session enforces the invariant

`backend/app/saas/db.py` `tenant_session(tenant_id)`:

1. Opens a Session from the process-wide engine (which authenticates as
   the superuser).
2. Executes `SET LOCAL ROLE aerogrid_app` — switches to the
   non-superuser role for the lifetime of the transaction. Reverts on
   commit or rollback.
3. Executes `SELECT set_config('app.tenant_id', :tid, true)`. The `true`
   argument is the parameterizable equivalent of `SET LOCAL`, so the
   setting reverts at the end of the transaction.

Because step 2 removes the superuser bypass and step 3 sets the GUC, the
subsequent queries are RLS-filtered. If step 3 is forgotten, the policy
returns zero rows, not all rows, because the unset case is handled.

## 6. Findings

### F-1 — Over-grant of `SELECT` on `tenants` to `aerogrid_app` (resolved by this PR)

Observed: `aerogrid_app` holds `SELECT` on `tenants` (section 4.4).
Tenants is not under RLS (section 4.1). Consequence: a code path that
opened `tenant_session` and queried `tenants` would see **every tenant
row**, not just the caller's, and would not raise an error.

Current exposure: none. The three code paths that read from `tenants`
(`get_tenant_plan` in `quota.py`; `create_checkout_session` and
`get_subscription` in `billing_routes.py`) all use `admin_session`,
which runs as the superuser and is explicitly marked as cross-tenant
administrative work. But the grant is unnecessary and contradicts the
least-privilege posture of `aerogrid_app`.

Remediation: migration `004_tenants_least_privilege.sql` revokes
`SELECT` on `tenants` from `aerogrid_app`. After this migration, a
tenant session that queries `tenants` fails at the SQL layer with
`InsufficientPrivilege`, not at the application layer. A new test in
`test_rls_isolation.py::test_app_role_cannot_read_tenants` proves the
revoke.

### F-2 — PERMISSIVE policies (documentation only)

Both policies are `PERMISSIVE`. PERMISSIVE policies are OR-ed; a second
permissive policy would widen access. If a future migration ever needs
to add a narrowing policy (e.g., a read-only role, an audit role), it
must be declared `AS RESTRICTIVE`; the current migrations do not yet
have such a policy and do not need one. Documented here so the decision
is on the record.

### F-3 — Policy role list is `{public}` (documentation only)

Both policies apply to all roles. This is the correct default: it means
any role that ever gains access to the tables is subject to the policy.
No action required.

## 7. Test coverage

`test_rls_isolation.py` (8 tests):

    test_tenant_sees_only_its_own_missions
    test_app_role_with_unset_guc_sees_zero_rows
    test_tenant_cannot_select_other_tenants_row_by_id
    test_tenant_cannot_insert_mission_for_other_tenant
    test_tenant_cannot_update_row_to_other_tenant
    test_tenant_delete_does_not_affect_other_tenant
    test_tenant_cannot_delete_other_tenants_row_by_id
    test_cascade_delete_on_tenant_removes_missions

New test added by this PR:

    test_app_role_cannot_read_tenants  (proves F-1 remediation)

`test_saas_quota.py` (2 Postgres tests) and `test_saas_routes.py`
(6 DB-backed tests) exercise the same invariant through the HTTP layer.

## 8. Residual risks

R-1. The superuser `aerogrid` bypasses RLS unconditionally, so any
     session that runs without `SET LOCAL ROLE aerogrid_app` has full
     cross-tenant access. The invariant is upheld by convention in
     `db.py`, not by a technical barrier. Reviewed: the only
     production-adjacent callers of `admin_session` are `get_tenant_plan`
     and the two billing-route handlers, all of which need cross-tenant
     visibility. No other handler uses `admin_session`.

R-2. Tenant JWTs are signed with a secret from `AEROGRID_JWT_SECRET`.
     A leaked signing secret allows forging a token for any tenant. This
     is out of scope for a database-level audit; the signing secret
     handling is reviewed in `app/saas/auth.py`.

R-3. The audit was performed against a locally running PostgreSQL 16.
     The CI job `rls-isolation` applies the same migrations to an
     ephemeral PostgreSQL 16 container before running the same test
     modules; the CI pass is independent evidence that the migrations
     are portable.

## 9. Certification

Within the scope defined in section 2, tenant isolation on the `missions`
and `quota_usage` tables is enforced by PostgreSQL at the database
layer, and the `aerogrid_app` role that executes tenant-scoped queries
cannot bypass that enforcement. `F-1` was the only gap identified by
this audit; it is remediated by migration `004` in this same PR and
proven closed by `test_app_role_cannot_read_tenants`. `F-2` and `F-3`
are documentation-only notes, not gaps.

Signed: Kian Mansouri Jamshidi
