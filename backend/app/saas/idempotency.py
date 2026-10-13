"""Webhook idempotency store.

Stripe delivers webhook events at least once and may retry on transient
failures. The handler must therefore deduplicate on the event ID before
performing side effects, so a duplicate delivery does not double-charge
or double-credit.

The store is defined as a runtime-checkable Protocol with two methods:

    already_seen(event_id) -> bool
    record(event_id, event_type) -> None

PostgresIdempotencyStore is the production implementation. It uses the
stripe_events table created by migration 002; the primary key on
event_id gives the uniqueness guarantee and the ON CONFLICT DO NOTHING
in record makes the insert idempotent even under concurrent delivery of
the same event.

FakeIdempotencyStore is a plain-dict in-memory double for tests. It is
not durable and does not survive process restart; it exists only so the
webhook route tests do not need PostgreSQL.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable

from sqlalchemy import text

from app.saas.db import admin_session


@runtime_checkable
class IdempotencyStore(Protocol):
    """Tracks which webhook events have been processed."""

    def already_seen(self, event_id: str) -> bool:
        """Return True if the event has been recorded before."""
        ...

    def record(self, event_id: str, event_type: str) -> None:
        """Record an event ID. Duplicate calls are no-ops."""
        ...


class PostgresIdempotencyStore:
    """Durable idempotency store backed by the stripe_events table."""

    def already_seen(self, event_id: str) -> bool:
        with admin_session() as s:
            row = s.execute(
                text("SELECT 1 FROM stripe_events WHERE event_id = :e"),
                {"e": event_id},
            ).first()
            return row is not None

    def record(self, event_id: str, event_type: str) -> None:
        with admin_session() as s:
            s.execute(
                text(
                    "INSERT INTO stripe_events (event_id, event_type) "
                    "VALUES (:e, :t) ON CONFLICT (event_id) DO NOTHING"
                ),
                {"e": event_id, "t": event_type},
            )


@dataclass
class FakeIdempotencyStore:
    """In-memory store for tests. Not durable across process restarts."""

    _seen: dict[str, str] = field(default_factory=dict)

    def already_seen(self, event_id: str) -> bool:
        return event_id in self._seen

    def record(self, event_id: str, event_type: str) -> None:
        self._seen.setdefault(event_id, event_type)

    def size(self) -> int:
        return len(self._seen)
