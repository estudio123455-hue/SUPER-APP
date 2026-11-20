"""Reactive EventBus handlers for Media AI sales attribution (Law 1)."""

from app.core.database import get_session_factory
from app.core.event_bus import InMemoryEventBus
from app.modules.commerce.public_api import OrderPaidEvent, OrderPlacedEvent
from app.modules.media_ai.application.use_cases import RecordVideoConversionUseCase
from app.modules.media_ai.infrastructure.repositories import (
    SqlAlchemyMediaJobRepository,
    SqlAlchemyScheduledPostRepository,
)


async def on_order_placed(event: OrderPlacedEvent) -> None:
    """Attributes Cash on Delivery order conversions to the originating video job."""
    if event.source_job_id is None:
        return
    session_factory = get_session_factory()
    async with session_factory() as session:
        use_case = RecordVideoConversionUseCase(
            job_repository=SqlAlchemyMediaJobRepository(session),
            post_repository=SqlAlchemyScheduledPostRepository(session),
        )
        await use_case.execute(
            source_job_id=event.source_job_id,
            order_total_cents=event.total_cents,
        )


async def on_order_paid(event: OrderPaidEvent) -> None:
    """Attributes Wallet-paid order conversions to the originating video job."""
    if event.source_job_id is None:
        return
    session_factory = get_session_factory()
    async with session_factory() as session:
        use_case = RecordVideoConversionUseCase(
            job_repository=SqlAlchemyMediaJobRepository(session),
            post_repository=SqlAlchemyScheduledPostRepository(session),
        )
        await use_case.execute(
            source_job_id=event.source_job_id,
            order_total_cents=event.total_cents,
        )


def register_media_ai_event_handlers(bus: InMemoryEventBus) -> None:
    """Subscribes Media AI attribution handlers to Commerce order events."""
    bus.subscribe(OrderPlacedEvent, on_order_placed)
    bus.subscribe(OrderPaidEvent, on_order_paid)
