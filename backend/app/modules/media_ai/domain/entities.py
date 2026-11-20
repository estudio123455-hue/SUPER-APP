"""Pure domain entities and value objects for the Media AI bounded context (Law 3)."""

from dataclasses import dataclass, field, replace
from datetime import UTC, date, datetime
from enum import StrEnum
from uuid import UUID, uuid4

from app.modules.media_ai.domain.exceptions import (
    InvalidJobStateTransitionError,
    InvalidMediaSourceError,
)


class JobType(StrEnum):
    """Supported AI & video processing job types in the Studio."""

    VIRAL_SHORT_CLIP = "VIRAL_SHORT_CLIP"
    AUTO_CAPTIONS_WHISPER = "AUTO_CAPTIONS_WHISPER"
    AI_OUTFIT_RECOMMENDATION = "AI_OUTFIT_RECOMMENDATION"
    PRODUCT_SHOWCASE_VIDEO = "PRODUCT_SHOWCASE_VIDEO"


class ContentNiche(StrEnum):
    """Multi-niche production templates for script and retention generation."""

    DESK_SETUP_UGC = "DESK_SETUP_UGC"
    RAP_CULTURE_VIRAL = "RAP_CULTURE_VIRAL"
    YOUTUBE_HIGHLIGHT_CLIP = "YOUTUBE_HIGHLIGHT_CLIP"
    MENSWEAR_LOOKBOOK = "MENSWEAR_LOOKBOOK"


class JobStatus(StrEnum):
    """Asynchronous lifecycle states of a MediaJob."""

    QUEUED = "QUEUED"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class PublishingSlot(StrEnum):
    """Daily two-videos-per-day publishing slots (Midday 12:30 & Evening 19:30)."""

    SLOT_1_MIDDAY = "SLOT_1_MIDDAY"
    SLOT_2_EVENING = "SLOT_2_EVENING"


@dataclass(frozen=True, kw_only=True)
class MediaJob:
    """Immutable domain entity representing a heavy AI/Video background job (Law 5)."""

    id: UUID = field(default_factory=uuid4)
    creator_id: UUID
    job_type: JobType
    content_niche: ContentNiche = ContentNiche.DESK_SETUP_UGC
    source_url_or_prompt: str
    linked_product_id: UUID | None = None
    use_real_pipeline: bool = False
    burn_subtitles: bool = True
    status: JobStatus = JobStatus.QUEUED
    progress_percent: int = 0
    result_payload: dict[str, str] | None = None
    error_message: str | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def __post_init__(self) -> None:
        cleaned_source = self.source_url_or_prompt.strip()
        if not cleaned_source:
            raise InvalidMediaSourceError("source_url_or_prompt cannot be empty.")
        object.__setattr__(self, "source_url_or_prompt", cleaned_source)

        if not (0 <= self.progress_percent <= 100):
            raise InvalidMediaSourceError(
                f"progress_percent must be between 0 and 100 (got {self.progress_percent})."
            )

    def mark_processing(self, progress: int = 25) -> "MediaJob":
        """Transitions job to PROCESSING with updated progress_percent."""
        if self.status in {JobStatus.COMPLETED, JobStatus.FAILED}:
            raise InvalidJobStateTransitionError(
                current_status=self.status.value,
                target_status=JobStatus.PROCESSING.value,
            )
        if not (0 < progress < 100):
            raise InvalidMediaSourceError(
                "Processing progress must be strictly between 1 and 99."
            )
        return replace(
            self,
            status=JobStatus.PROCESSING,
            progress_percent=progress,
            error_message=None,
        )

    def mark_completed(self, result_payload: dict[str, str]) -> "MediaJob":
        """Transitions job to COMPLETED (progress_percent = 100) with output artifacts."""
        if self.status == JobStatus.FAILED:
            raise InvalidJobStateTransitionError(
                current_status=self.status.value,
                target_status=JobStatus.COMPLETED.value,
            )
        if not result_payload:
            raise InvalidMediaSourceError(
                "Completed MediaJob must include a non-empty result_payload."
            )
        return replace(
            self,
            status=JobStatus.COMPLETED,
            progress_percent=100,
            result_payload=dict(result_payload),
            error_message=None,
        )

    def mark_failed(self, error_message: str) -> "MediaJob":
        """Transitions job to FAILED with an error description."""
        if self.status == JobStatus.COMPLETED:
            raise InvalidJobStateTransitionError(
                current_status=self.status.value,
                target_status=JobStatus.FAILED.value,
            )
        cleaned_error = error_message.strip() or "Unknown processing error"
        return replace(
            self,
            status=JobStatus.FAILED,
            error_message=cleaned_error,
        )

    @property
    def artifacts_purged(self) -> bool:
        """Returns True when heavy disk artifacts for this job have been purged."""
        return bool(
            self.result_payload
            and self.result_payload.get("artifacts_purged", "").lower() == "true"
        )

    def mark_artifacts_purged(self) -> "MediaJob":
        """Marks heavy disk artifacts as purged while preserving job metadata and ROI attribution."""
        updated_payload = dict(self.result_payload) if self.result_payload else {}
        updated_payload["artifacts_purged"] = "true"
        return replace(self, result_payload=updated_payload)


@dataclass(frozen=True, kw_only=True)
class ScheduledPost:
    """Immutable domain entity tracking a scheduled video post and its attributed sales."""

    id: UUID = field(default_factory=uuid4)
    job_id: UUID
    creator_id: UUID
    platform: str = "TIKTOK"
    scheduled_date: date
    slot: PublishingSlot
    conversions_count: int = 0
    revenue_attributed_cents: int = 0
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def __post_init__(self) -> None:
        normalized_platform = self.platform.strip().upper()
        if not normalized_platform:
            raise ValueError("ScheduledPost platform cannot be empty.")
        object.__setattr__(self, "platform", normalized_platform)
        if self.conversions_count < 0 or self.revenue_attributed_cents < 0:
            raise ValueError("Conversions and revenue cannot be negative.")

    def record_conversion(self, order_total_cents: int) -> "ScheduledPost":
        """Increments conversions_count and adds attributed revenue in integer cents."""
        if order_total_cents <= 0:
            raise ValueError("order_total_cents must be strictly positive (> 0).")
        return replace(
            self,
            conversions_count=self.conversions_count + 1,
            revenue_attributed_cents=self.revenue_attributed_cents + order_total_cents,
        )
