"""SQLAlchemy models for the multi-tenant SaaS layer.

The models here are the minimum needed to demonstrate row-level
security isolation:

  - Tenant:  one row per customer.
  - Mission: a tenant-scoped record, one row per mission configuration.

Every tenant-scoped model inherits from ``TenantScopedBase``, which
carries the ``tenant_id`` foreign key. The corresponding RLS policy is
created in the migration SQL, not in Python, because policies are a
PostgreSQL feature and expressing them through an ORM would obscure
the security-relevant detail.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """Shared declarative base for every model."""


class Tenant(Base):
    """A customer account.

    Tenants are the top-level partition. They are not tenant-scoped
    themselves; RLS does not apply to the tenants table.
    """

    __tablename__ = "tenants"

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    slug: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    display_name: Mapped[str] = mapped_column(String(256), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC)
    )


class TenantScopedBase(Base):
    """Abstract base for tables with a tenant_id column under RLS."""

    __abstract__ = True

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
    )


class Mission(TenantScopedBase):
    """A tenant-owned mission configuration.

    Used by the RLS isolation tests and by the SaaS admin panel. The
    columns are deliberately minimal; the point of this table is the
    tenant_id + RLS policy pair, not the mission content.
    """

    __tablename__ = "missions"

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(String(256), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC)
    )
