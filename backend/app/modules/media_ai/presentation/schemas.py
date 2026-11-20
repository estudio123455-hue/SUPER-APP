"""Pydantic v2 request and response schemas for the Media AI presentation layer."""

from datetime import UTC, date, datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.modules.media_ai.domain.entities import (
    ContentNiche,
    JobStatus,
    JobType,
    PublishingSlot,
)


class EnqueueMediaJobRequest(BaseModel):
    """Payload for enqueuing an asynchronous video or AI processing job."""

    model_config = ConfigDict(from_attributes=True)

    job_type: JobType
    content_niche: ContentNiche = Field(
        default=ContentNiche.DESK_SETUP_UGC,
        description="Multi-niche script and retention template.",
    )
    source_url_or_prompt: str = Field(
        ...,
        min_length=3,
        max_length=2000,
        examples=["https://storage.superapp.io/raw/unboxing_ergo.mp4"],
    )
    linked_product_id: UUID | None = Field(
        default=None,
        description="Optional Commerce catalog product UUID to embed in the AI/Video job.",
    )
    use_real_pipeline: bool = Field(
        default=False,
        description="When True, runs real yt-dlp (720p) + faster-whisper (int8 CPU) + FFmpeg (9:16).",
    )
    burn_subtitles: bool = Field(
        default=True,
        description="When True, burns TikTok-styled bold subtitles into the vertical 9:16 MP4.",
    )


class MediaJobResponse(BaseModel):
    """Public representation of a MediaJob and its asynchronous progress/output."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    creator_id: UUID
    job_type: JobType
    content_niche: ContentNiche
    source_url_or_prompt: str
    linked_product_id: UUID | None
    use_real_pipeline: bool = False
    burn_subtitles: bool = True
    status: JobStatus
    progress_percent: int
    result_payload: dict[str, str] | None
    error_message: str | None
    artifacts_purged: bool = False
    created_at: datetime


class ScheduleMediaPostRequest(BaseModel):
    """Payload for scheduling a MediaJob into one of the daily publishing slots."""

    model_config = ConfigDict(from_attributes=True)

    platform: str = Field(default="TIKTOK", examples=["TIKTOK", "INSTAGRAM_REELS"])
    scheduled_date: date = Field(
        default_factory=lambda: datetime.now(UTC).date(),
        description="Target publication date (YYYY-MM-DD).",
    )
    slot: PublishingSlot


class ScheduledPostResponse(BaseModel):
    """Public representation of a scheduled video post and its attributed sales."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    job_id: UUID
    creator_id: UUID
    platform: str
    scheduled_date: date
    slot: PublishingSlot
    conversions_count: int
    revenue_attributed_cents: int
    ics_download_url: str
    created_at: datetime


class DailyStreakProgressResponse(BaseModel):
    """Public response summarizing the 2-videos/day goal and scheduled publications."""

    model_config = ConfigDict(from_attributes=True)

    target_date: date
    scheduled_today_count: int
    daily_goal: int
    goal_completed: bool
    total_conversions: int
    total_revenue_attributed_cents: int
    scheduled_posts: list[ScheduledPostResponse]


class NichePerformanceMetricResponse(BaseModel):
    """Performance and ROI metrics for a specific ContentNiche vertical."""

    model_config = ConfigDict(from_attributes=True)

    content_niche: ContentNiche
    total_videos_created: int
    total_videos_scheduled: int
    conversions_count: int
    revenue_attributed_cents: int
    conversions_per_video: float


class NichePerformanceAnalyticsResponse(BaseModel):
    """Aggregated content ROI analytics across all ContentNiche verticals."""

    model_config = ConfigDict(from_attributes=True)

    top_performing_niche: ContentNiche | None = None
    total_videos_created: int
    total_videos_scheduled: int
    total_conversions: int
    total_revenue_attributed_cents: int
    niches: list[NichePerformanceMetricResponse]


class MediaArtifactCleanupRequest(BaseModel):
    """Optional JSON body for purging expired heavy media artifacts."""

    model_config = ConfigDict(from_attributes=True)

    retention_days: int = Field(
        default=30,
        ge=0,
        le=3650,
        description="Purge artifacts for completed/failed jobs older than this many days.",
    )


class MediaArtifactCleanupResponse(BaseModel):
    """Summary of purged expired media artifacts while preserving ROI attribution metrics."""

    model_config = ConfigDict(from_attributes=True)

    retention_days: int
    jobs_scanned: int
    files_deleted: int
    bytes_reclaimed: int
    retained_metrics_count: int
