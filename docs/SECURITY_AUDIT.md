# Security Audit — AeroGrid-XAI

**Scope:** OWASP Top 10 (2021 edition) review of the FastAPI backend,
the React frontend, and the multi-tenant SaaS layer.

**Environment:** Native macOS, single-host deployment per roadmap
decision D2. No containers, no orchestration, no cloud VMs.

**Method:** Each of the OWASP Top 10 categories is assessed against
the current code. Where a mitigation exists, the file that implements
it is named. Where a gap remains, it is recorded with a severity and a
follow-up.

---

## A01 — Broken Access Control

**Status: Mitigated.**

- Tenant isolation is enforced at the database layer with PostgreSQL
  Row-Level Security. Every tenant-scoped table carries a
  `tenant_id` column under an RLS policy. The application role
  `aerogrid_app` cannot read the `tenants` table at all (migration
  `004_tenants_least_privilege.sql`). See `docs/ISOLATION_AUDIT.md`
  for the audit and the CI job `rls-isolation` that exercises the
  policy on every PR.
- The JWT's `sub` claim is the tenant UUID; the `role` claim is one
  of `viewer`, `admin`, `superadmin`. `require_role()` in
  `backend/app/saas/auth.py` enforces a minimum role per route.
  `superadmin` is the only role that bypasses the tenant filter, and
  it is issued only out of band by the operator, never via
  `/auth/token` or `/auth/signup`.
- `/auth/signup` and `/auth/token` always issue `Role.ADMIN`, never
  `superadmin`. An endpoint callable by any tenant cannot be a path
  to a cross-tenant credential.

**Residual risk:** None identified.

---

## A02 — Cryptographic Failures

**Status: Mitigated.**

- Passwords are hashed with pgcrypto `crypt(password,
  gen_salt('bf', 12))`. bcrypt with cost 12 in 2025 is roughly 250 ms
  per verification on a modern CPU, which is the standard trade-off
  between brute-force cost and legitimate latency.
- Password verification and hashing both happen inside PostgreSQL.
  The plaintext is bound as a SQL parameter and never becomes a
  Python string that could be logged or introspected.
- JWTs are signed with HS256. The signing secret is read from
  `AEROGRID_JWT_SECRET`. If the environment is not `development` and
  the secret is unset or equals the documented dev default, the
  process refuses to start (`signing_secret()` in
  `backend/app/saas/auth.py`).
- The dev secret `DEV_SECRET` is a fixed string, and it is guarded:
  the process cannot start with it when `AEROGRID_ENV != development`.
- No session cookies are used. Authentication is entirely via the
  `Authorization: Bearer` header, which is not automatically sent by
  browsers on cross-origin requests and is therefore immune to CSRF
  by construction.

**Residual risk:** No key rotation policy for `AEROGRID_JWT_SECRET`.
Rotation requires invalidating all issued tokens, which for a 24-hour
TTL means a scheduled maintenance window. Acceptable for the current
scale; a refresh-token mechanism would allow graceful rotation and is
a follow-up.

---

## A03 — Injection

**Status: Mitigated.**

- All SQL is parameterized. There is no string interpolation into
  SQL anywhere in `backend/app/saas/`. Every query that takes input
  uses `text()` with named parameters.
- No ORM `execute()` with f-strings, no `.format()`, no `%` string
  formatting on any query.
- The frontend never sends unescaped HTML to the API. React escapes
  by default; the codebase contains no `dangerouslySetInnerHTML`.
- The architecture grammar and Z3 encoder in
  `backend/app/verification/` parse structured JSON, not strings.
  User-supplied architecture parameters are range-checked before
  they reach the encoder.

**Residual risk:** None identified.

---

## A04 — Insecure Design

**Status: Partially mitigated.**

- The epistemic hierarchy (`docs/EPISTEMIC_HIERARCHY_AUDIT.md`) and
  the two-tier XAI architecture (`backend/app/control/tier1.py`,
  `tier2.py`) enforce a design separation between decision authority
  and prediction. The static analyzer
  (`backend/app/control/static_analyzer.py`) verifies at build time
  that Tier 2 cannot reach the action interface.
- The rate limit rules in `backend/app/middleware/rate_limit.py` are
  set at the operation level, not the request level. `/auth/signup`
  is 3/min, `/auth/token` is 5/min, expensive operations
  (`/discovery/run`, `/design/explore`) are 30/min, and the Stripe
  webhook is exempt because Stripe has its own retry policy.

**Residual risk:** No threat model document. `docs/DID/SRS.md` is
functional, not a threat model. A STRIDE-based threat model is a
follow-up.

---

## A05 — Security Misconfiguration

**Status: Mitigated by this sprint.**

- Security headers added in `backend/app/middleware/security_headers.py`:
  `X-Content-Type-Options`, `X-Frame-Options`, `Referrer-Policy`,
  `Permissions-Policy`, `Cross-Origin-Opener-Policy`,
  `Cross-Origin-Resource-Policy`, `Content-Security-Policy`, and
  (outside development) `Strict-Transport-Security`.
- CORS is explicit. In development, the origins are
  `http://localhost:5173` and `http://127.0.0.1:5173`. In any other
  environment, `AEROGRID_ALLOWED_ORIGINS` must be set; the process
  refuses to start otherwise.
- `allow_credentials=False` — we do not use cookies.
- The `/docs` endpoint is enabled in development. In production, it
  should be disabled by setting `docs_url=None, redoc_url=None` on
  the `FastAPI()` constructor. This is a follow-up gated on a
  production environment variable.

**Residual risk:** Swagger UI is exposed in development. It is a
development convenience, not a leak of secrets — the OpenAPI schema
is not sensitive — but a production deployment should disable it.

---

## A06 — Vulnerable and Outdated Components

**Status: Mitigated.**

- Backend: `environment.yml` pins major versions for Python packages
  and conda-forge packages. `ruff`, `mypy`, and `pytest` run on every
  PR. `pip` has no direct dependencies outside the pinned list.
- Frontend: `package-lock.json` is committed; `npm ci` is used in CI.
  `oxlint` and `tsc -b` run on every PR.
- The `prometheus-fastapi-instrumentator` version was pinned at
  7.0.0 in the environment; upgrading is a deliberate act, not a
  side effect of another change.
- Homebrew (`prometheus`, `grafana`, `gh`) updates on operator
  request; brew-formulae are semantically-versioned and their
  changelogs are the release notes.

**Residual risk:** No automated dependency vulnerability scanner
(Dependabot, `pip-audit`, `npm audit`). A follow-up PR will add
`pip-audit` and `npm audit --audit-level=high` to the CI matrix. Until
then, the operator is expected to run them manually before a release.

---

## A07 — Identification and Authentication Failures

**Status: Partially mitigated.**

- Login errors are uniform. `/auth/token` returns a single 401
  `{"detail": "invalid credentials"}` for wrong slug, wrong password,
  and null password_hash. The three cases are indistinguishable in the
  response.
- The database lookup runs unconditionally for every login attempt,
  so timing does not leak slug existence.
- Passwords have a 12-character minimum, enforced at the Pydantic
  layer of `/auth/signup` and in the `SignupForm.tsx` client.
- `/auth/signup` rejects duplicate slugs with 409, distinct from the
  422 for validation failures. This is a deliberate choice: the slug
  is user-supplied by the same caller, so the caller already knows
  whether they chose that slug. Uniform-401 leak concerns do not
  apply.
- Rate limiting on `/auth/*` is new in this PR. Sign-in is 5/min and
  signup is 3/min per IP. Redis-backed, shared across workers.

**Residual risk:**
- No account lockout after N failed attempts. The rate limiter
  provides a bound but does not lock the account.
- No multi-factor authentication. Not planned for the initial release.
- No password reset flow. Users with a lost password must be
  re-provisioned by an operator.
- No email verification.

---

## A08 — Software and Data Integrity Failures

**Status: Mitigated.**

- Git history is on GitHub with branch protection: six required
  contexts, `enforce_admins: true`, force-push blocked, deletion
  blocked. See the roadmap decision D4 and `.github/workflows/ci.yml`.
- Every commit is authored by the sole contributor and carries no
  AI-assisted or co-authored-by attribution.
- No unsigned binary artifacts are downloaded at runtime. Homebrew
  packages are verified by brew's own checksum mechanism; conda-forge
  packages are verified by conda's own.
- JWT signatures are verified with PyJWT using HS256 and the process
  secret. Expiry is checked.

**Residual risk:** No signed commits (GPG or SSH signing). A follow-up
PR will add commit signing for releases.

---

## A09 — Security Logging and Monitoring Failures

**Status: Mitigated by s11-2.**

- Prometheus scrapes the FastAPI `/metrics` endpoint every 15 s.
  `http_requests_total{handler, method, status}` provides a per-route
  request count and status breakdown.
- `http_request_duration_seconds{handler}` provides latency
  percentiles.
- Grafana renders the four-panel dashboard committed at
  `infrastructure/monitoring/grafana/dashboards/aerogrid-backend.json`.
- PostgreSQL logs auth failures (uniform 401) at the database level
  in `data/postgresql/server.log`.

**Residual risk:**
- No alerting rules. Thresholds are drawn on the dashboard but no
  alerts fire. A follow-up PR will add Prometheus alert rules for
  5xx rate and p99 latency.
- No centralized log aggregation. Each service writes to its own
  log file.

---

## A10 — Server-Side Request Forgery (SSRF)

**Status: Not applicable.**

- The backend does not make outbound HTTP requests based on
  user-supplied URLs. The only outbound HTTP client is the Stripe SDK
  in `backend/app/saas/billing.py`, and its target URLs are
  hardcoded by the SDK, not derived from user input.
- The frontend fetches from a fixed set of relative paths under
  `/api/*`, and the Vite dev server proxies them to a hardcoded
  backend URL.

**Residual risk:** None identified.

---

## Summary table

| Category | Status | Mitigation |
|---|---|---|
| A01 Broken Access Control | ✅ Mitigated | PostgreSQL RLS, JWT role claims, no superadmin issuance via user endpoints |
| A02 Cryptographic Failures | ✅ Mitigated | pgcrypto bcrypt 12, HS256 JWT, dev-secret guard |
| A03 Injection | ✅ Mitigated | Parameterized SQL, React escaping, structured JSON input |
| A04 Insecure Design | 🟡 Partial | Rate limit rules, no STRIDE threat model |
| A05 Security Misconfiguration | ✅ Mitigated | Security headers, explicit CORS, HSTS outside dev |
| A06 Vulnerable Components | ✅ Mitigated | Version pins, `npm ci`, brew/conda checksums |
| A07 Auth Failures | 🟡 Partial | Uniform 401, rate limiting, no MFA / lockout / reset |
| A08 Software Integrity | ✅ Mitigated | Branch protection, no unsigned binaries, signed JWTs |
| A09 Logging & Monitoring | ✅ Mitigated | Prometheus + Grafana via s11-2 |
| A10 SSRF | ✅ N/A | No user-controlled outbound URLs |

---

## Follow-ups

1. **STRIDE threat model** as `docs/THREAT_MODEL.md`.
2. **Automated dependency scanning** in CI (`pip-audit`, `npm audit`).
3. **Prometheus alert rules** for 5xx rate and p99 latency.
4. **Signed commits** for release tags.
5. **Password reset flow**.
6. **Optional MFA** for admin accounts.
7. **Disable `/docs` in production** via an environment variable.
