"""Row-level security isolation tests.

These tests exercise the PostgreSQL RLS policy on the missions table
directly. They require a running PostgreSQL with the RLS migration
applied. Start it with scripts/start_services.sh; the module skips
cleanly if the database is not reachable, so the current CI backend
job (which does not start PostgreSQL) is unaffected.

A dedicated CI job that starts PostgreSQL, applies the migration, and
runs these tests is the correct follow-up; the skip is a temporary
accommodation, not the final arrangement.
"""

from __future__ import annotations

import uuid
from collections.abc import Iterator

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DatabaseError

from app.saas.db import admin_session, get_engine, tenant_session


def _postgres_reachable() -> bool:
    try:
        with get_engine().connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False


pytestmark = pytest.mark.skipif(
    not _postgres_reachable(),
    reason=(
        "PostgreSQL is not reachable; start it with scripts/start_services.sh "
        "and apply backend/app/saas/migrations/001_rls_setup.sql"
    ),
)


@pytest.fixture()
def two_tenants() -> Iterator[tuple[uuid.UUID, uuid.UUID]]:
    """Provision two tenants. Cleaned up at the end of the test.

    Uses admin_session because the tenants table has no RLS policy; only
    missions is scoped. Teardown relies on ON DELETE CASCADE, which is a
    database-level operation and is not blocked by FORCE ROW LEVEL
    SECURITY on the missions table.
    """
    with admin_session() as s:
        a = uuid.uuid4()
        b = uuid.uuid4()
        s.execute(
            text("INSERT INTO tenants (id, slug, display_name) VALUES (:id, :slug, :name)"),
            {"id": str(a), "slug": f"t-a-{a.hex[:8]}", "name": "Tenant A"},
        )
        s.execute(
            text("INSERT INTO tenants (id, slug, display_name) VALUES (:id, :slug, :name)"),
            {"id": str(b), "slug": f"t-b-{b.hex[:8]}", "name": "Tenant B"},
        )
    try:
        yield (a, b)
    finally:
        with admin_session() as s:
            s.execute(
                text("DELETE FROM tenants WHERE id IN (:a, :b)"),
                {"a": str(a), "b": str(b)},
            )


def _insert_mission(tenant_id: uuid.UUID, name: str) -> uuid.UUID:
    mid = uuid.uuid4()
    with tenant_session(tenant_id) as s:
        s.execute(
            text("INSERT INTO missions (id, tenant_id, name) VALUES (:id, :tid, :name)"),
            {"id": str(mid), "tid": str(tenant_id), "name": name},
        )
    return mid


def _all_mission_ids(tenant_id: uuid.UUID) -> set[uuid.UUID]:
    with tenant_session(tenant_id) as s:
        rows = s.execute(text("SELECT id FROM missions")).all()
        return {uuid.UUID(str(r[0])) for r in rows}


# --- isolation ------------------------------------------------------------


def test_tenant_sees_only_its_own_missions(
    two_tenants: tuple[uuid.UUID, uuid.UUID],
) -> None:
    a, b = two_tenants
    ma = _insert_mission(a, "a-mission")
    mb = _insert_mission(b, "b-mission")
    assert _all_mission_ids(a) == {ma}
    assert _all_mission_ids(b) == {mb}


def test_app_role_with_unset_guc_sees_zero_rows(
    two_tenants: tuple[uuid.UUID, uuid.UUID],
) -> None:
    """Under the non-superuser application role, an unset app.tenant_id
    filters every row out.

    The RLS policy wraps the GUC read in NULLIF(..., '') before casting
    to uuid, because on this PostgreSQL an unset custom GUC returns the
    empty string rather than NULL, and ''::uuid raises
    InvalidTextRepresentation. With the NULLIF guard, the unset case
    yields NULL, the comparison tenant_id = NULL is NULL, the policy
    treats that as FALSE, and no row passes. This is the safety
    property that protects against a code path that forgets to set the
    GUC: it sees nothing rather than everything.

    The session must switch to aerogrid_app, because the default role
    in the connection pool is the schema-owning superuser, which
    bypasses RLS unconditionally. That is why the test issues SET LOCAL
    ROLE itself rather than using admin_session.
    """
    a, _ = two_tenants
    _insert_mission(a, "a-mission")
    with admin_session() as s:
        s.execute(text("SET LOCAL ROLE aerogrid_app"))
        rows = s.execute(text("SELECT id FROM missions")).all()
    assert rows == []


def test_tenant_cannot_select_other_tenants_row_by_id(
    two_tenants: tuple[uuid.UUID, uuid.UUID],
) -> None:
    """An explicit WHERE id = <other tenant's mission id> still returns
    nothing, because RLS is applied before the WHERE clause."""
    a, b = two_tenants
    _insert_mission(a, "a-mission")
    mb = _insert_mission(b, "b-mission")
    with tenant_session(a) as s:
        rows = s.execute(
            text("SELECT id FROM missions WHERE id = :id"),
            {"id": str(mb)},
        ).all()
    assert rows == []


def test_tenant_cannot_insert_mission_for_other_tenant(
    two_tenants: tuple[uuid.UUID, uuid.UUID],
) -> None:
    """The WITH CHECK clause rejects an INSERT whose tenant_id does not
    match the GUC."""
    a, b = two_tenants
    with pytest.raises(DatabaseError), tenant_session(a) as s:
        s.execute(
            text("INSERT INTO missions (id, tenant_id, name) VALUES (:id, :tid, :name)"),
            {"id": str(uuid.uuid4()), "tid": str(b), "name": "wrong"},
        )


def test_tenant_cannot_update_row_to_other_tenant(
    two_tenants: tuple[uuid.UUID, uuid.UUID],
) -> None:
    """An UPDATE that changes tenant_id to another tenant is rejected
    by the WITH CHECK clause."""
    a, b = two_tenants
    ma = _insert_mission(a, "a-mission")
    with pytest.raises(DatabaseError), tenant_session(a) as s:
        s.execute(
            text("UPDATE missions SET tenant_id = :new WHERE id = :id"),
            {"new": str(b), "id": str(ma)},
        )


def test_tenant_delete_does_not_affect_other_tenant(
    two_tenants: tuple[uuid.UUID, uuid.UUID],
) -> None:
    """A DELETE issued under tenant A does not touch tenant B's rows,
    even when the DELETE has no WHERE clause."""
    a, b = two_tenants
    _insert_mission(a, "a-mission")
    mb = _insert_mission(b, "b-mission")
    with tenant_session(a) as s:
        s.execute(text("DELETE FROM missions"))
    assert _all_mission_ids(a) == set()
    assert _all_mission_ids(b) == {mb}


def test_tenant_cannot_delete_other_tenants_row_by_id(
    two_tenants: tuple[uuid.UUID, uuid.UUID],
) -> None:
    a, b = two_tenants
    ma = _insert_mission(a, "a-mission")
    mb = _insert_mission(b, "b-mission")
    with tenant_session(b) as s:
        s.execute(
            text("DELETE FROM missions WHERE id = :id"),
            {"id": str(ma)},
        )
    assert _all_mission_ids(a) == {ma}
    assert _all_mission_ids(b) == {mb}


def test_cascade_delete_on_tenant_removes_missions(
    two_tenants: tuple[uuid.UUID, uuid.UUID],
) -> None:
    """ON DELETE CASCADE is a database-level operation and is not
    blocked by FORCE ROW LEVEL SECURITY on the missions table."""
    a, b = two_tenants
    _insert_mission(a, "a-mission")
    _insert_mission(b, "b-mission")
    with admin_session() as s:
        s.execute(text("DELETE FROM tenants WHERE id = :id"), {"id": str(a)})
    # Tenant A's missions must be gone.
    with admin_session() as s:
        rows = s.execute(
            text("SELECT id FROM missions WHERE tenant_id = :tid"),
            {"tid": str(a)},
        ).all()
    assert rows == []
    # Tenant B's missions must remain; confirm via tenant-scoped session.
    assert len(_all_mission_ids(b)) == 1


def test_app_role_cannot_read_tenants(
    two_tenants: tuple[uuid.UUID, uuid.UUID],
) -> None:
    """The tenants table is not tenant-scoped and has no RLS policy.

    Isolation of tenants relies on the fact that no tenant-scoped code
    path queries it. This test makes that property explicit: a session
    that has switched to aerogrid_app cannot read from tenants at all,
    so a future code path that accidentally queries it under a tenant
    session fails loudly with InsufficientPrivilege instead of silently
    returning every tenant row. See docs/ISOLATION_AUDIT.md finding F-1.
    """
    a, _ = two_tenants
    with pytest.raises(DatabaseError), tenant_session(a) as s:
        s.execute(text("SELECT id FROM tenants")).all()
