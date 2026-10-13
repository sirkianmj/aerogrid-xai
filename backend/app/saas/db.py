"""SQLAlchemy engine and tenant-scoped session helpers.

Every table that carries tenant data has a ``tenant_id`` column and a
PostgreSQL row-level security policy keyed on
``current_setting('app.tenant_id')``. This module provides:

  - ``get_engine()``               a cached SQLAlchemy Engine
  - ``tenant_session(tenant_id)``  a context manager yielding a Session
                                   with app.tenant_id set for the
                                   lifetime of the transaction
  - ``admin_session()``            a context manager yielding a Session
                                   without setting app.tenant_id, for
                                   cross-tenant administrative work

The RLS policy filters every SELECT, UPDATE, and DELETE on tenant-scoped
tables to the rows whose tenant_id matches the GUC. The GUC is set with
SET LOCAL inside the connection's transaction so it does not leak into
the next user of the connection pool.

Isolation is enforced by PostgreSQL, not by application code. A query
that omits a WHERE tenant_id clause still returns zero rows for the
wrong tenant.
"""

from __future__ import annotations

import os
from collections.abc import Iterator
from contextlib import contextmanager
from functools import lru_cache
from uuid import UUID

from sqlalchemy import Engine, create_engine, text
from sqlalchemy.orm import Session, sessionmaker


def database_url() -> str:
    """Return the SQLAlchemy URL for the application database.

    Reads ``AEROGRID_DATABASE_URL`` from the environment, falling back
    to the local development database started by scripts/start_services.sh.
    """
    return os.environ.get(
        "AEROGRID_DATABASE_URL",
        "postgresql+psycopg2://aerogrid@127.0.0.1:5432/aerogrid",
    )


@lru_cache(maxsize=1)
def get_engine() -> Engine:
    """Return the process-wide SQLAlchemy Engine."""
    return create_engine(database_url(), future=True)


@lru_cache(maxsize=1)
def _session_factory() -> sessionmaker[Session]:
    return sessionmaker(bind=get_engine(), future=True, expire_on_commit=False)


@contextmanager
def tenant_session(tenant_id: UUID | str) -> Iterator[Session]:
    """Yield a Session scoped to one tenant.

    Executes ``SET LOCAL app.tenant_id = '<uuid>'`` inside the session's
    transaction, so PostgreSQL RLS filters every query on tenant-scoped
    tables to the rows belonging to that tenant. The setting resets when
    the transaction ends.

    Args:
        tenant_id: The tenant UUID, as a UUID or a string.
    """
    tid = str(tenant_id)
    # Basic format check to catch a caller passing the wrong argument.
    UUID(tid)
    factory = _session_factory()
    session = factory()
    try:
        # The process connects as the schema-owning superuser (needed
        # for migrations and tenant provisioning). Superusers bypass
        # row-level security unconditionally, so every tenant-scoped
        # query must run under a non-superuser role. SET LOCAL ROLE
        # switches the current role for the duration of the transaction
        # and reverts on commit or rollback; the underlying connection
        # is returned to the pool still authenticated as the superuser.
        session.execute(text("SET LOCAL ROLE aerogrid_app"))
        # SET LOCAL does not accept bind parameters in PostgreSQL:
        # "SET LOCAL app.tenant_id = $1" is a syntax error. The
        # parameterizable form is set_config(name, value, is_local),
        # where the third argument true means "local to the current
        # transaction", equivalent to SET LOCAL.
        session.execute(
            text("SELECT set_config('app.tenant_id', :tid, true)"),
            {"tid": tid},
        )
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


@contextmanager
def admin_session() -> Iterator[Session]:
    """Yield a Session with no tenant scope.

    Used by tests and by the tenant-provisioning path, which must see
    across tenants to create them. Production request handlers must
    never call this.
    """
    factory = _session_factory()
    session = factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def reset_engine_cache() -> None:
    """Clear cached engine and sessionmaker. Used by tests after they
    change AEROGRID_DATABASE_URL."""
    get_engine.cache_clear()
    _session_factory.cache_clear()
