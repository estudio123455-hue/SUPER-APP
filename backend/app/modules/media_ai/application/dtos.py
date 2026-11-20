"""Application commands and DTOs for the Media AI module."""

from dataclasses import dataclass
from datetime import date, datetime
from uuid import UUID

from app.modules.media_ai.domain.entities import (
    ContentNiche,
    JobStatus,
    JobType,
    MediaJob,
    PublishingSlot,
    ScheduledPost,
)


@dataclass(frozen=True, kw_only=True)
class EnqueueMediaJobCommand:
    """Command to enqueue an asynchronous video or AI processing job."""

    creator_id: UUID
    job_type: JobType
    content_niche: ContentNiche = ContentNiche.DESK_SETUP_UGC
    source_url_or_prompt: str
    linked_product_id: UUID | None = None
    use_real_pipeline: bool = False
    burn_subtitles: bool = True


@dataclass(frozen=True, kw_only=True)
class ScheduleMediaPostCommand:
    """Command to schedule a MediaJob into one of the daily publishing slots."""

    job_id: UUID
    creator_id: UUID
    platform: str
    scheduled_date: date
    slot: PublishingSlot


@dataclass(frozen=True, kw_only=True)
class MediaJobDTO:
    """Application DTO representing a MediaJob."""

    id: UUID
    creator_id: UUID
    job_type: JobType
    content_niche: ContentNiche
    source_url_or_prompt: str
    linked_product_id: UUID | None
    use_real_pipeline: bool
    burn_subtitles: bool
    status: JobStatus
    progress_percent: int
    result_payload: dict[str, str] | None
    error_message: str | None
    artifacts_purged: bool = False
    created_at: datetime

    @classmethod
    def from_entity(cls, job: MediaJob) -> "MediaJobDTO":
        return cls(
            id=job.id,
            creator_id=job.creator_id,
            job_type=job.job_type,
            content_niche=job.content_niche,
            source_url_or_prompt=job.source_url_or_prompt,
            linked_product_id=job.linked_product_id,
            use_real_pipeline=job.use_real_pipeline,
            burn_subtitles=job.burn_subtitles,
            status=job.status,
            progress_percent=job.progress_percent,
            result_payload=dict(job.result_payload) if job.result_payload else None,
            error_message=job.error_message,
            artifacts_purged=job.artifacts_purged,
            created_at=job.created_at,
        )


@dataclass(frozen=True, kw_only=True)
class ScheduledPostDTO:
    """Application DTO representing a scheduled video publication and its sales metrics."""

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

    @classmethod
    def from_entity(cls, post: ScheduledPost) -> "ScheduledPostDTO":
        return cls(
            id=post.id,
            job_id=post.job_id,
            creator_id=post.creator_id,
            platform=post.platform,
            scheduled_date=post.scheduled_date,
            slot=post.slot,
            conversions_count=post.conversions_count,
            revenue_attributed_cents=post.revenue_attributed_cents,
            ics_download_url=f"/api/v1/media-ai/jobs/{post.job_id}/download-ics",
            created_at=post.created_at,
        )


@dataclass(frozen=True, kw_only=True)
class DailyStreakProgressDTO:
    """Application DTO summarizing the creator's 2-videos/day goal and scheduled posts."""

    target_date: date
    scheduled_today_count: int
    daily_goal: int
    goal_completed: bool
    total_conversions: int
    total_revenue_attributed_cents: int
    scheduled_posts: tuple[ScheduledPostDTO, ...]


@dataclass(frozen=True, kw_only=True)
class NichePerformanceMetricDTO:
    """Performance and ROI metrics for a specific ContentNiche vertical."""

    content_niche: ContentNiche
    total_videos_created: int
    total_videos_scheduled: int
    conversions_count: int
    revenue_attributed_cents: int
    conversions_per_video: float


@dataclass(frozen=True, kw_only=True)
class NichePerformanceAnalyticsDTO:
    """Aggregated content ROI analytics across all ContentNiche verticals."""

    top_performing_niche: ContentNiche | None
    total_videos_created: int
    total_videos_scheduled: int
    total_conversions: int
    total_revenue_attributed_cents: int
    niches: tuple[NichePerformanceMetricDTO, ...]


@dataclass(frozen=True, kw_only=True)
class CleanupExpiredMediaArtifactsResultDTO:
    """Application DTO summarizing expired media artifact cleanup while preserving ROI metrics."""

    retention_days: int
    jobs_scanned: int
    files_deleted: int
    bytes_reclaimed: int
    retained_metrics_count: int
