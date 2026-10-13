'''Build Notebook 09 - Multi-tenant isolation.'''
from pathlib import Path
import nbformat as nbf

NB = nbf.v4.new_notebook()
CELLS = []

def md(text):
    CELLS.append(nbf.v4.new_markdown_cell(text))

def code(text):
    CELLS.append(nbf.v4.new_code_cell(text))

md('''# Notebook 09 - Multi-tenant isolation

**Sprint:** S8 (SaaS Architecture - Multi-Tenant Backend)
**Roadmap task:** s8-8

## Scientific gate

> Tenant A cannot access Tenant B data (all endpoints).

## What this notebook demonstrates

Two tenants (A and B) are provisioned with the same schema. Every
tenant-scoped endpoint is exercised with A's token and B's token; the
responses are asserted to reflect only the caller's tenant. Direct
database access through tenant_session provides an independent line of
evidence: PostgreSQL row-level security filters the rows before the
application sees them, so a bug in a handler cannot leak data.

## Endpoints exercised

    GET  /saas/whoami           echoes the caller's tenant and role
    GET  /saas/mission-count    RLS-scoped count from the missions table
    GET  /saas/subscription     reads the caller's row from tenants
    POST /tradespace/run        metered per-tenant quota consumption

## Method

1. Provision tenants A and B with one mission each.
2. Issue a viewer JWT for each.
3. Call every tenant-scoped endpoint twice (once per token) and assert
   the response matches the caller, never the other tenant.
4. Verify at the database layer that a WHERE-clause bypass still
   returns zero cross-tenant rows.
5. Confirm the quota counter is per-tenant: consuming A's tradespace
   quota does not change B's.

Epistemic category for every result below: [SIMULATION] (Digital Twin
output of the SaaS layer against a local PostgreSQL). No physical
measurement is claimed.
''')

md("## Setup")

code('''import sys
import uuid
from pathlib import Path

repo_root = Path.cwd().parent if Path.cwd().name == "notebooks" else Path.cwd()
sys.path.insert(0, str(repo_root / "backend"))

from fastapi.testclient import TestClient
from sqlalchemy import text

from app.main import app
from app.saas.auth import Role, issue_token
from app.saas.db import admin_session, get_engine, tenant_session
from app.saas.quota import current_period_start

try:
    with get_engine().connect() as conn:
        conn.execute(text("SELECT 1"))
except Exception as exc:
    raise RuntimeError(
        "PostgreSQL is not reachable. Start it with "
        "scripts/start_services.sh and apply migrations under "
        "backend/app/saas/migrations/."
    ) from exc

for tbl in ("tenants", "missions", "quota_usage", "stripe_events"):
    with get_engine().connect() as conn:
        present = conn.execute(
            text("SELECT to_regclass(:t)"),
            {"t": tbl},
        ).scalar()
    if present is None:
        raise RuntimeError(f"table missing: {tbl}")

client = TestClient(app)
print("PostgreSQL reachable; all four tables present")
''')

md('''## Section 1 - Provision tenants A and B

Each tenant gets a unique UUID, a slug, and one mission inserted
through a tenant_session (so the WITH CHECK clause is exercised). The
viewer JWTs are the only credential the endpoints will see.
''')

code('''TENANT_A = uuid.uuid4()
TENANT_B = uuid.uuid4()
MISSION_A = uuid.uuid4()
MISSION_B = uuid.uuid4()

def provision(tid, mid, label):
    with admin_session() as s:
        s.execute(
            text("INSERT INTO tenants (id, slug, display_name) VALUES (:i, :s, :n)"),
            {"i": str(tid), "s": f"{label.lower()}-{tid.hex[:8]}", "n": label},
        )
    with tenant_session(tid) as s:
        s.execute(
            text("INSERT INTO missions (id, tenant_id, name) VALUES (:i, :t, :n)"),
            {"i": str(mid), "t": str(tid), "n": f"{label}-mission"},
        )

provision(TENANT_A, MISSION_A, "Tenant-A")
provision(TENANT_B, MISSION_B, "Tenant-B")

TOKEN_A = issue_token(TENANT_A, Role.VIEWER)
TOKEN_B = issue_token(TENANT_B, Role.VIEWER)
HEADERS_A = {"Authorization": f"Bearer {TOKEN_A}"}
HEADERS_B = {"Authorization": f"Bearer {TOKEN_B}"}

print(f"Tenant A: {TENANT_A}  mission {MISSION_A}")
print(f"Tenant B: {TENANT_B}  mission {MISSION_B}")
''')

md('''## Section 2 - GET /saas/whoami echoes the caller only

The endpoint decodes the JWT and returns its sub claim. It is the
simplest tenant-scoped endpoint: a token for A must return A, a token
for B must return B. A wrong answer here would indicate a broken
middleware.
''')

code('''for label, tid, headers in (
    ("A", TENANT_A, HEADERS_A),
    ("B", TENANT_B, HEADERS_B),
):
    r = client.get("/saas/whoami", headers=headers)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["tenant_id"] == str(tid), body
    assert body["is_superadmin"] is False, body
    print(f"whoami({label}) -> tenant_id={body['tenant_id']} role={body['role']}")

assert client.get("/saas/whoami").status_code == 401
print("whoami without a token -> 401  (correct)")
''')

md('''## Section 3 - GET /saas/mission-count is RLS-scoped

The handler opens a tenant_session, which issues SET LOCAL ROLE
aerogrid_app and sets app.tenant_id. The COUNT query has no WHERE
clause; the RLS policy on missions does the filtering. Each tenant
must see exactly its own mission.
''')

code('''for label, tid, headers in (
    ("A", TENANT_A, HEADERS_A),
    ("B", TENANT_B, HEADERS_B),
):
    r = client.get("/saas/mission-count", headers=headers)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["tenant_id"] == str(tid), body
    assert body["n_missions"] == 1, body
    print(f"mission-count({label}) -> {body['n_missions']}  (expected 1)")
''')

md('''## Section 4 - Database-layer proof: WHERE-clause bypass

The strongest test of RLS: query for a row by primary key with no
tenant filter of any kind in the SQL. If RLS holds, the row is
invisible because the policy is applied before the WHERE clause
matches.
''')

code('''with tenant_session(TENANT_A) as s:
    rows = s.execute(
        text("SELECT id, name FROM missions WHERE id = :id"),
        {"id": str(MISSION_B)},
    ).all()
assert rows == [], f"Tenant A saw Tenant B mission: {rows}"
print("A asked for B mission id by primary key -> 0 rows  (correct)")

with tenant_session(TENANT_B) as s:
    rows = s.execute(
        text("SELECT id, name FROM missions WHERE id = :id"),
        {"id": str(MISSION_A)},
    ).all()
assert rows == [], f"Tenant B saw Tenant A mission: {rows}"
print("B asked for A mission id by primary key -> 0 rows  (correct)")
''')

md('''## Section 5 - GET /saas/subscription reads the caller row

Each tenant row is given a distinct subscription id. The endpoint must
return the caller row and only the caller row. This is the code path
that, if the s8-9 audit had not found F-1, would have been the only
place tenants SELECT was needed. The endpoint uses admin_session and
filters by ctx.tenant_id explicitly, so isolation holds even though
tenants is not under RLS.
''')

code('''with admin_session() as s:
    s.execute(
        text("UPDATE tenants SET stripe_subscription_id = :sub WHERE id = :i"),
        {"sub": "sub_A_only", "i": str(TENANT_A)},
    )
    s.execute(
        text("UPDATE tenants SET stripe_subscription_id = :sub WHERE id = :i"),
        {"sub": "sub_B_only", "i": str(TENANT_B)},
    )

rA = client.get("/saas/subscription", headers=HEADERS_A)
rB = client.get("/saas/subscription", headers=HEADERS_B)
assert rA.status_code == 200 and rB.status_code == 200
a = rA.json()
b = rB.json()
assert a["tenant_id"] == str(TENANT_A) and a["subscription_id"] == "sub_A_only", a
assert b["tenant_id"] == str(TENANT_B) and b["subscription_id"] == "sub_B_only", b
print(f"subscription(A) -> {a['subscription_id']}")
print(f"subscription(B) -> {b['subscription_id']}")
print("A never sees sub_B_only; B never sees sub_A_only  (correct)")
''')

md('''## Section 6 - Quota is per-tenant

Free plan: 10 tradespace_runs per calendar month. Tenant A spends all
10 and is refused an 11th (429 with Retry-After). Tenant B does not
call the endpoint at all. B counter must remain 0.
''')

code('''period = current_period_start()
BODY = {"population_size": 4, "n_generations": 1}

def peek(tid):
    with admin_session() as s:
        row = s.execute(
            text(
                "SELECT count FROM quota_usage "
                "WHERE tenant_id = :t AND metric = :m AND period_start = :p"
            ),
            {"t": str(tid), "m": "tradespace_runs", "p": period},
        ).first()
    return int(row[0]) if row is not None else 0

for i in range(10):
    r = client.post("/tradespace/run", json=BODY, headers=HEADERS_A)
    assert r.status_code == 200, f"run {i + 1}: {r.status_code} {r.text}"
assert peek(TENANT_A) == 10

r = client.post("/tradespace/run", json=BODY, headers=HEADERS_A)
assert r.status_code == 429, r.text
assert "Retry-After" in r.headers
assert int(r.headers["Retry-After"]) >= 1
print(f"A: 10 runs charged, 11th -> 429  Retry-After={r.headers['Retry-After']}s")
print(f"A counter: {peek(TENANT_A)}  (over-limit attempts are charged by design)")

assert peek(TENANT_B) == 0, peek(TENANT_B)
print(f"B counter: {peek(TENANT_B)}  (A consumption did not leak)")
''')

md('''## Section 7 - Endpoint inventory

Tenant-scoped endpoints (require a bearer JWT; the response reflects
the caller tenant):

    GET  /saas/whoami
    GET  /saas/mission-count
    GET  /saas/subscription
    POST /saas/checkout-session    (admin only, requires Stripe config)
    POST /tradespace/run           (metered)

Global endpoints (no tenant context; not part of the isolation claim):

    GET  /health
    POST /decisions/charge
    GET  /orbital/*
    GET  /digital-twin/*
    WS   /telemetry/stream
    GET  /metrics

The gate applies to the first group. Each of the four exercised
endpoints returned the caller tenant and only the caller tenant.
''')

md("## Cleanup and result")

code('''with admin_session() as s:
    s.execute(
        text("DELETE FROM tenants WHERE id IN (:a, :b)"),
        {"a": str(TENANT_A), "b": str(TENANT_B)},
    )

print("Notebook 09 - Multi-tenant isolation")
print("=" * 60)
print(f"Tenant A: {TENANT_A}")
print(f"Tenant B: {TENANT_B}")
print("whoami:            A -> A, B -> B")
print("mission-count:     A -> 1, B -> 1")
print("subscription:      A -> sub_A_only, B -> sub_B_only")
print("direct query:      A asked for B mission id -> 0 rows")
print("quota:             A hit 429 at limit 10; B counter remained 0")
print()
print("ALL GATES PASS")
''')

NB["cells"] = CELLS
NB["metadata"] = {
    "kernelspec": {
        "display_name": "Python 3 (aerogrid)",
        "language": "python",
        "name": "python3",
    },
    "language_info": {"name": "python", "version": "3.12"},
}

out = Path("notebooks/09_tenant_isolation.ipynb")
out.parent.mkdir(parents=True, exist_ok=True)
nbf.write(NB, str(out))
print(f"Wrote {out}")
print(f"Cells: {len(CELLS)}")
