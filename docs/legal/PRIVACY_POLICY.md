# Privacy Policy

**Version:** 0.1 (template)
**Last modified:** 2026-10-15

> **NOTICE:** This is a starting template. It is not legal advice and
> has not been reviewed by counsel. Before deploying AeroGrid-XAI as a
> public service, engage a qualified attorney to confirm compliance
> with GDPR, CCPA, and any other applicable privacy regime.

## 1. What we collect

**Account data (required to sign up):**
- Tenant slug — your login handle
- Display name — shown in the operator's admin interface
- Password — hashed with bcrypt (cost 12) by PostgreSQL's pgcrypto
  module. The plaintext is never stored, never logged, and never
  leaves the process boundary as a Python string.

**Session data (created automatically when you sign in):**
- A JWT, stored in your browser's `localStorage` under the key
  `aerogrid.token`. The token contains your tenant UUID and role.
  Expires after 24 hours.

**Request metadata (created automatically):**
- Client IP address, request path, response status, and request
  duration. Recorded in Prometheus for operational monitoring. Rate
  limiting uses the client IP as a Redis key with a short TTL
  (60 seconds).

**Content you create:**
- Mission configurations, architecture definitions, satellite and
  drone designs, CLEAR-D runs, XAI trace runs, and any artifacts you
  export. Stored in the platform's PostgreSQL database and, for
  exports, in MinIO object storage.

## 2. What we do NOT collect

- No cookies. Authentication uses an `Authorization: Bearer` header.
- No third-party analytics, advertising identifiers, or tracking
  pixels.
- No biometric data, no precise geolocation, no camera or microphone
  access.
- No email addresses. Signup does not request one; the platform does
  not send email.

## 3. How we use the data

- **Account data** — to authenticate you, to keep your tenant isolated
  from other tenants via PostgreSQL Row-Level Security, and to
  associate your designs with your account.
- **Session data** — to keep you signed in across page loads until
  the JWT expires.
- **Request metadata** — to detect abuse (rate limiting), diagnose
  incidents (latency and error rate), and generate the operator's
  Grafana dashboard.
- **Content** — to serve it back to you. Nothing is analysed for
  marketing, shared with data brokers, or used to train external
  models.

## 4. Where data is stored

Everything runs on the operator's local macOS deployment.

- PostgreSQL 16 (port 5432) — accounts, missions, architectures.
- Redis 8 (port 6379) — rate-limit counters with a 60-second TTL.
- MinIO (ports 9000/9001) — object storage for exports.
- Prometheus (port 9090) — operational metrics with 15-day retention.

No data leaves the machine unless you deliberately export it. The
Stripe integration (if enabled) is the sole exception: to process a
paid subscription, Stripe receives the billing details you enter on
Stripe's own hosted checkout page. Stripe's privacy policy governs
that data. AeroGrid-XAI itself never sees or stores card numbers.

## 5. Data retention

- **Account data** — until you request deletion, or until the operator
  deletes an inactive tenant.
- **Session tokens** — expire 24 hours after issue. No server-side
  session table; the JWT is self-contained.
- **Rate-limit counters** — 60-second TTL, deleted automatically.
- **Prometheus metrics** — 15-day retention, then deleted by the
  Prometheus TSDB retention policy.
- **Content you delete** — removed immediately from PostgreSQL. Backups
  and Prometheus samples may retain traces for up to 15 days.

## 6. Your rights

You can request:

- **Access** — a copy of everything stored about your tenant.
- **Correction** — fixes to your display name or slug.
- **Deletion** — full removal of your tenant and all associated
  content. Deletion is immediate at the database level and cannot be
  undone.
- **Portability** — a JSON export of your missions, architectures, and
  designs.

To exercise any of these, contact sirkianmj@forgex4.com. There is no
self-service deletion UI in this version; a follow-up will add one.

## 7. Children

The Service is not directed at children under 16. Signup requires
acceptance of the Terms of Service, and the Service assumes no
knowledge of a user's age.

## 8. International transfers

The Service runs on a single host. There is no international transfer
of personal data. If the operator deploys the Service in multiple
regions in the future, this section will be updated.

## 9. Security

- Passwords hashed with pgcrypto bcrypt, cost factor 12.
- Tenant data isolated at the PostgreSQL layer via Row-Level Security.
- All HTTP requests carry a Content Security Policy, `X-Frame-Options`,
  and other defense-in-depth headers.
- Authentication endpoints are rate limited per IP.
- JWTs signed with HS256; the signing secret is required in every
  environment except local development.

No security mechanism is perfect. If you believe you have found a
vulnerability, report it to sirkianmj@forgex4.com rather than
disclosing it publicly.

## 10. Changes to this policy

The operator may update this policy. Material changes will be
announced through the Service. Continued use after the effective date
constitutes acceptance.

## 11. Contact

Privacy questions or data requests: sirkianmj@forgex4.com
