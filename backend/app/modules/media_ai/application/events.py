"""Domain events emitted by the Media AI bounded context."""

from dataclasses import dataclass
from uuid import UUID

from app.core.event_bus import DomainEvent


@dataclass(frozen=True, kw_only=True)
class MediaJobQueuedEvent(DomainEvent):
    """Published when a new MediaJob is enqueued for background execution."""

    job_id: UUID
    creator_id: UUID
    job_type: str
    linked_product_id: UUID | None


@dataclass(frozen=True, kw_only=True)
class MediaJobCompletedEvent(DomainEvent):
    """Published when a MediaJob finishes processing successfully."""

    job_id: UUID
    creator_id: UUID
    job_type: str
    linked_product_id: UUID | None
    result_payload: dict[str, str]


@dataclass(frozen=True, kw_only=True)
class MediaJobFailedEvent(DomainEvent):
    """Published when a MediaJob fails during background processing."""

    job_id: UUID
    creator_id: UUID
    job_type: str
    error_message: str
