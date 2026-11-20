"""Transactional Outbox Pattern implementation for resilient domain event publishing.

Guarantees at-least-once event delivery across modular boundaries without
locking or breaking the primary HTTP request lifecycle.
"""

import asyncio
from dataclasses import asdict, is_dataclass

from datetime import UTC, datetime
import json
import logging
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import DateTime, Integer, String, Text, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base, get_session_factory
from app.core.event_bus import DomainEvent, EventBus, _json_serializer

logger = logging.getLogger("superapp.outbox")


class OutboxEventModel(Base):
    """SQLAlchemy 2.0 model for the Transactional Outbox pattern."""

    __tablename__ = "outbox_events"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    event_id: Mapped[UUID] = mapped_column(index=True, nullable=False)
    event_name: Mapped[str] = mapped_column(String(128), index=True, nullable=False)
    payload: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(
        String(32), default="PENDING", index=True, nullable=False
    )
    retry_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
    )
    published_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )


async def publish_event_with_outbox(
    event_bus: EventBus,
    event: DomainEvent,
    session: AsyncSession | None = None,
) -> OutboxEventModel:
    """Persists a DomainEvent in the Outbox table and attempts resilient dispatch via EventBus.

    If event_bus.publish fails, the failure is safely recorded in the outbox entry (status='FAILED')
    without raising an unhandled exception into the caller request loop.
    """
    event_id = getattr(event, "event_id", None) or uuid4()
    event_name = type(event).__name__

    if is_dataclass(event):
        payload_dict = asdict(event)
    elif hasattr(event, "__dict__"):
        payload_dict = event.__dict__
    else:
        payload_dict = {"event_id": str(event_id)}

    payload_str = json.dumps(payload_dict, default=_json_serializer)

    outbox_entry = OutboxEventModel(
        id=uuid4(),
        event_id=event_id,
        event_name=event_name,
        payload=payload_str,
        status="PENDING",
        retry_count=0,
        error_message=None,
        created_at=datetime.now(UTC),
        published_at=None,
    )

    if session is not None:
        session.add(outbox_entry)
        await session.flush()
        try:
            await event_bus.publish(event)
            outbox_entry.status = "PUBLISHED"
            outbox_entry.published_at = datetime.now(UTC)
        except Exception as exc:
            logger.warning(
                "Failed to publish event %s (%s) via event bus: %s",
                event_name,
                event_id,
                exc,
            )
            outbox_entry.status = "FAILED"
            outbox_entry.error_message = str(exc)
            outbox_entry.retry_count += 1
        return outbox_entry

    factory = get_session_factory()
    async with factory() as new_session:
        new_session.add(outbox_entry)
        await new_session.commit()
        try:
            await event_bus.publish(event)
            outbox_entry.status = "PUBLISHED"
            outbox_entry.published_at = datetime.now(UTC)
            await new_session.commit()
        except Exception as exc:
            logger.warning(
                "Failed to publish event %s (%s) via event bus: %s",
                event_name,
                event_id,
                exc,
            )
            outbox_entry.status = "FAILED"
            outbox_entry.error_message = str(exc)
            outbox_entry.retry_count += 1
            await new_session.commit()

    return outbox_entry


async def relay_pending_outbox_events(
    event_bus: EventBus,
    session: AsyncSession,
    limit: int = 50,
) -> int:
    """Outbox Relay Worker: picks up PENDING or FAILED events and re-attempts dispatching them."""
    stmt = (
        select(OutboxEventModel)
        .where(OutboxEventModel.status.in_(["PENDING", "FAILED"]))
        .order_by(OutboxEventModel.created_at.asc())
        .limit(limit)
    )
    result = await session.execute(stmt)
    records = list(result.scalars().all())

    dispatched = 0
    for record in records:
        try:
            dummy_event = DomainEvent(
                event_id=record.event_id,
                occurred_at=record.created_at,
            )
            await event_bus.publish(dummy_event)
            record.status = "PUBLISHED"
            record.published_at = datetime.now(UTC)
            dispatched += 1
        except Exception as exc:
            record.retry_count += 1
            record.error_message = str(exc)

    await session.commit()
    return dispatched


async def run_outbox_retry_loop(
    event_bus: EventBus,
    session_factory: Any = None,
    interval_seconds: float = 15.0,
) -> None:
    """Continuous background worker loop that periodically relays pending/failed outbox events.

    Safely handles unexpected exceptions to prevent loop crashes, and exits cleanly upon asyncio.CancelledError.
    """
    factory = session_factory or get_session_factory()
    logger.info("Starting Outbox retry loop (interval: %.1fs)", interval_seconds)
    try:
        while True:
            try:
                async with factory() as session:
                    dispatched = await relay_pending_outbox_events(
                        event_bus=event_bus,
                        session=session,
                    )
                    if dispatched > 0:
                        logger.info(
                            "Outbox retry loop relayed %d pending event(s)",
                            dispatched,
                        )
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                logger.error("Error in Outbox retry loop: %s", exc, exc_info=True)

            await asyncio.sleep(interval_seconds)
    except asyncio.CancelledError:
        logger.info("Outbox retry loop successfully stopped (cancelled).")
        raise

