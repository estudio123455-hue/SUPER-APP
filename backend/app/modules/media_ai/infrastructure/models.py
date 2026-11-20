"""SQLAlchemy 2.0 models for the Media AI module isolated in 'media_ai_schema' (Law 2).

No ForeignKeys to identity_schema or commerce_schema are permitted; creator_id,
linked_product_id, and job_id are stored as pure indexed UUIDs.
"""

from datetime import UTC, date, datetime
from uuid import UUID, uuid4

from sqlalchemy import BigInteger, Boolean, Date, DateTime, Integer, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import build_schema_base

MediaAiBase = build_schema_base("media_ai")


class MediaJobModel(MediaAiBase):
    """Database representation of a MediaJob in media_ai_schema."""

    __tablename__ = "media_jobs"

    id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )
    creator_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        index=True,
        nullable=False,
    )
    job_type: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
    )
    content_niche: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        default="DESK_SETUP_UGC",
    )
    source_url_or_prompt: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )
    linked_product_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        index=True,
        nullable=True,
    )
    use_real_pipeline: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )
    burn_subtitles: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
    )
    status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="QUEUED",
    )
    progress_percent: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )
    result_payload_json: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    error_message: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
    )


class ScheduledPostModel(MediaAiBase):
    """Database representation of a ScheduledPost and its sales attribution in media_ai_schema."""

    __tablename__ = "scheduled_posts"

    id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )
    job_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        unique=True,
        index=True,
        nullable=False,
    )
    creator_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        index=True,
        nullable=False,
    )
    platform: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="TIKTOK",
    )
    scheduled_date: Mapped[date] = mapped_column(
        Date,
        index=True,
        nullable=False,
    )
    slot: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
    )
    conversions_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )
    revenue_attributed_cents: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"),
        nullable=False,
        default=0,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
    )
