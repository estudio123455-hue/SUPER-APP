"""Public API contract for the media_ai module (Law 1).

Other bounded contexts MUST ONLY import from this file when inspecting MediaJob
metadata or subscribing to Media AI events.
"""

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.media_ai.application.events import (
    MediaJobCompletedEvent,
    MediaJobFailedEvent,
    MediaJobQueuedEvent,
)
from app.modules.media_ai.domain.exceptions import MediaJobNotFoundError
from app.modules.media_ai.infrastructure.repositories import (
    SqlAlchemyMediaJobRepository,
)


@dataclass(frozen=True, kw_only=True)
class MediaJobPublicDTO:
    """Immutable cross-module representation of a MediaJob."""

    id: UUID
    creator_id: UUID
    job_type: str
    status: str
    progress_percent: int
    linked_product_id: UUID | None
    result_payload: dict[str, str] | None
    created_at: datetime


async def get_media_job_public_info(
    job_id: UUID,
    session: AsyncSession,
) -> MediaJobPublicDTO:
    """Public contract for other modules to inspect a MediaJob's state and output."""
    repository = SqlAlchemyMediaJobRepository(session)
    job = await repository.get_by_id(job_id)
    if job is None:
        raise MediaJobNotFoundError(str(job_id))

    return MediaJobPublicDTO(
        id=job.id,
        creator_id=job.creator_id,
        job_type=job.job_type.value,
        status=job.status.value,
        progress_percent=job.progress_percent,
        linked_product_id=job.linked_product_id,
        result_payload=dict(job.result_payload) if job.result_payload else None,
        created_at=job.created_at,
    )


__all__ = [
    "MediaJobCompletedEvent",
    "MediaJobFailedEvent",
    "MediaJobNotFoundError",
    "MediaJobPublicDTO",
    "MediaJobQueuedEvent",
    "get_media_job_public_info",
]
