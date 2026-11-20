"""Abstract repository, catalog lookup, artifact generator, and async dispatcher ports (Law 3)."""

from dataclasses import dataclass
from datetime import date, datetime
from typing import Protocol
from uuid import UUID

from app.modules.media_ai.domain.entities import (
    MediaJob,
    PublishingSlot,
    ScheduledPost,
)


@dataclass(frozen=True, kw_only=True)
class LinkedProductInfo:
    """Pure domain value object holding metadata of a linked catalog product."""

    id: UUID
    sku: str
    title: str
    price_cents: int
    is_active: bool


class MediaJobRepository(Protocol):
    """Port for persisting and querying MediaJob entities."""

    async def get_by_id(self, job_id: UUID) -> MediaJob | None:
        """Finds a MediaJob by its unique UUID."""
        ...

    async def list_by_creator(self, creator_id: UUID) -> list[MediaJob]:
        """Lists all MediaJobs created by a specific user."""
        ...

    async def list_expired_terminal_jobs(
        self,
        cutoff: datetime,
        creator_id: UUID | None = None,
    ) -> list[MediaJob]:
        """Lists COMPLETED or FAILED MediaJobs created strictly before cutoff."""
        ...

    async def save(self, job: MediaJob) -> MediaJob:
        """Persists a new or updated MediaJob entity."""
        ...


class ScheduledPostRepository(Protocol):
    """Port for persisting and querying ScheduledPost entities."""

    async def get_by_job_id(self, job_id: UUID) -> ScheduledPost | None:
        """Finds a ScheduledPost associated with a MediaJob."""
        ...

    async def get_by_date_and_slot(
        self,
        creator_id: UUID,
        scheduled_date: date,
        slot: PublishingSlot,
    ) -> ScheduledPost | None:
        """Finds an existing ScheduledPost for a creator on a specific date and slot."""
        ...

    async def list_by_creator(self, creator_id: UUID) -> list[ScheduledPost]:
        """Lists all ScheduledPosts belonging to a creator."""
        ...

    async def save(self, post: ScheduledPost) -> ScheduledPost:
        """Persists a new or updated ScheduledPost entity."""
        ...


class CatalogLookupPort(Protocol):
    """Port for verifying and retrieving product metadata from the Commerce catalog."""

    async def get_product_info(self, product_id: UUID) -> LinkedProductInfo | None:
        """Returns product metadata if the product exists and is active, or None."""
        ...

    async def get_cross_sell_bundle(self, product_id: UUID) -> dict | None:
        """Returns an AI smart cross-sell bundle recommendation for the product, or None."""
        ...


class MediaArtifactGeneratorPort(Protocol):
    """Port for generating physical .srt, .md, .json, .ics, and .mp4 media artifacts on disk."""

    def persist_job_artifacts(
        self,
        job: MediaJob,
        payload: dict[str, str],
        enable_real_media_pipeline: bool = False,
        burn_subtitles: bool = True,
    ) -> dict[str, str]:
        """Writes physical media artifacts and returns the enriched payload dictionary."""
        ...

    def read_srt_content(self, job_id: UUID) -> str | None:
        """Reads the generated captions.srt content for a completed job."""
        ...

    def read_script_markdown(self, job_id: UUID) -> str | None:
        """Reads the generated script_tiktok.md production guide for a completed job."""
        ...

    def get_mp4_file_path(self, job_id: UUID) -> str | None:
        """Returns the path to short_9x16.mp4 for a completed job, or None."""
        ...

    def persist_calendar_invite_ics(
        self,
        post: ScheduledPost,
        job: MediaJob,
    ) -> str:
        """Writes calendar_invite.ics (VCALENDAR/VEVENT/VALARM) and returns its file path."""
        ...

    def read_ics_content(self, job_id: UUID) -> str | None:
        """Reads the generated calendar_invite.ics content for a scheduled job."""
        ...

    def purge_job_artifacts(self, job_id: UUID) -> tuple[int, int]:
        """Deletes heavy physical artifacts for job_id and returns (files_deleted, bytes_reclaimed)."""
        ...


class AsyncJobDispatcherPort(Protocol):
    """Port for scheduling heavy media/AI jobs outside the HTTP main thread (Law 5)."""

    def dispatch(self, job_id: UUID) -> None:
        """Enqueues job_id for asynchronous execution off the request cycle."""
        ...
