"""SQLAlchemy 2.0 repositories, Commerce Public API adapter, Artifact/ICS/Video Generator & Worker."""

import asyncio
from datetime import UTC, date, datetime
import importlib.util
import json
from pathlib import Path
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.database import get_session_factory
from app.core.event_bus import event_bus
from app.modules.commerce.public_api import (
    ProductNotFoundError,
    get_cross_sell_recommendation_public,
    get_product_public_info,
)
from app.modules.media_ai.application.use_cases import ExecuteMediaJobUseCase
from app.modules.media_ai.domain.entities import (
    ContentNiche,
    JobStatus,
    JobType,
    MediaJob,
    PublishingSlot,
    ScheduledPost,
)
from app.modules.media_ai.domain.repositories import (
    AsyncJobDispatcherPort,
    CatalogLookupPort,
    LinkedProductInfo,
    MediaArtifactGeneratorPort,
    MediaJobRepository,
    ScheduledPostRepository,
)
from app.modules.media_ai.infrastructure.models import MediaJobModel, ScheduledPostModel
from app.modules.media_ai.infrastructure.video_pipeline import (
    MINIMAL_MP4_BYTES,
    RealVideoClipperPipeline,
)

BACKEND_ROOT_DIR = Path(__file__).resolve().parents[4]
MEDIA_OUTPUTS_DIR = get_settings().effective_media_outputs_dir


class SqlAlchemyMediaJobRepository(MediaJobRepository):
    """Adapter persisting MediaJob entities via SQLAlchemy 2.0 AsyncSession."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    @staticmethod
    def _to_domain(model: MediaJobModel) -> MediaJob:
        created_at = model.created_at
        if created_at.tzinfo is None:
            created_at = created_at.replace(tzinfo=UTC)
        payload: dict[str, str] | None = None
        if model.result_payload_json:
            loaded = json.loads(model.result_payload_json)
            payload = {str(k): str(v) for k, v in loaded.items()}
        niche_val = getattr(model, "content_niche", None) or "DESK_SETUP_UGC"
        real_pipe = bool(getattr(model, "use_real_pipeline", False))
        burn_subs = bool(getattr(model, "burn_subtitles", True))
        return MediaJob(
            id=model.id,
            creator_id=model.creator_id,
            job_type=JobType(model.job_type),
            content_niche=ContentNiche(niche_val),
            source_url_or_prompt=model.source_url_or_prompt,
            linked_product_id=model.linked_product_id,
            use_real_pipeline=real_pipe,
            burn_subtitles=burn_subs,
            status=JobStatus(model.status),
            progress_percent=int(model.progress_percent),
            result_payload=payload,
            error_message=model.error_message,
            created_at=created_at,
        )

    async def get_by_id(self, job_id: UUID) -> MediaJob | None:
        stmt = select(MediaJobModel).where(MediaJobModel.id == job_id)
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        return self._to_domain(model) if model is not None else None

    async def list_by_creator(self, creator_id: UUID) -> list[MediaJob]:
        stmt = (
            select(MediaJobModel)
            .where(MediaJobModel.creator_id == creator_id)
            .order_by(MediaJobModel.created_at.desc())
        )
        result = await self._session.execute(stmt)
        models = result.scalars().all()
        return [self._to_domain(m) for m in models]

    async def list_expired_terminal_jobs(
        self,
        cutoff: datetime,
        creator_id: UUID | None = None,
    ) -> list[MediaJob]:
        stmt = select(MediaJobModel).where(
            MediaJobModel.status.in_(
                [JobStatus.COMPLETED.value, JobStatus.FAILED.value]
            )
        )
        if creator_id is not None:
            stmt = stmt.where(MediaJobModel.creator_id == creator_id)
        stmt = stmt.order_by(MediaJobModel.created_at.asc())
        result = await self._session.execute(stmt)
        models = result.scalars().all()
        normalized_cutoff = (
            cutoff if cutoff.tzinfo is not None else cutoff.replace(tzinfo=UTC)
        )
        return [
            job
            for job in (self._to_domain(m) for m in models)
            if job.created_at < normalized_cutoff
        ]

    async def save(self, job: MediaJob) -> MediaJob:
        stmt = select(MediaJobModel).where(MediaJobModel.id == job.id)
        result = await self._session.execute(stmt)
        existing = result.scalar_one_or_none()

        payload_json = (
            json.dumps(job.result_payload) if job.result_payload is not None else None
        )

        if existing is None:
            model = MediaJobModel(
                id=job.id,
                creator_id=job.creator_id,
                job_type=job.job_type.value,
                content_niche=job.content_niche.value,
                source_url_or_prompt=job.source_url_or_prompt,
                linked_product_id=job.linked_product_id,
                use_real_pipeline=job.use_real_pipeline,
                burn_subtitles=job.burn_subtitles,
                status=job.status.value,
                progress_percent=job.progress_percent,
                result_payload_json=payload_json,
                error_message=job.error_message,
                created_at=job.created_at,
            )
            self._session.add(model)
        else:
            existing.content_niche = job.content_niche.value
            existing.use_real_pipeline = job.use_real_pipeline
            existing.burn_subtitles = job.burn_subtitles
            existing.status = job.status.value
            existing.progress_percent = job.progress_percent
            existing.result_payload_json = payload_json
            existing.error_message = job.error_message
            model = existing

        await self._session.commit()
        return self._to_domain(model)


class SqlAlchemyScheduledPostRepository(ScheduledPostRepository):
    """Adapter persisting ScheduledPost entities via SQLAlchemy 2.0 AsyncSession."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    @staticmethod
    def _to_domain(model: ScheduledPostModel) -> ScheduledPost:
        created_at = model.created_at
        if created_at.tzinfo is None:
            created_at = created_at.replace(tzinfo=UTC)
        sched_date = model.scheduled_date
        if isinstance(sched_date, str):
            sched_date = datetime.strptime(sched_date, "%Y-%m-%d").date()
        return ScheduledPost(
            id=model.id,
            job_id=model.job_id,
            creator_id=model.creator_id,
            platform=model.platform,
            scheduled_date=sched_date,
            slot=PublishingSlot(model.slot),
            conversions_count=int(model.conversions_count),
            revenue_attributed_cents=int(model.revenue_attributed_cents),
            created_at=created_at,
        )

    async def get_by_job_id(self, job_id: UUID) -> ScheduledPost | None:
        stmt = select(ScheduledPostModel).where(ScheduledPostModel.job_id == job_id)
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        return self._to_domain(model) if model is not None else None

    async def get_by_date_and_slot(
        self,
        creator_id: UUID,
        scheduled_date: date,
        slot: PublishingSlot,
    ) -> ScheduledPost | None:
        stmt = select(ScheduledPostModel).where(
            ScheduledPostModel.creator_id == creator_id,
            ScheduledPostModel.scheduled_date == scheduled_date,
            ScheduledPostModel.slot == slot.value,
        )
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        return self._to_domain(model) if model is not None else None

    async def list_by_creator(self, creator_id: UUID) -> list[ScheduledPost]:
        stmt = (
            select(ScheduledPostModel)
            .where(ScheduledPostModel.creator_id == creator_id)
            .order_by(
                ScheduledPostModel.scheduled_date.desc(),
                ScheduledPostModel.slot.asc(),
            )
        )
        result = await self._session.execute(stmt)
        models = result.scalars().all()
        return [self._to_domain(m) for m in models]

    async def save(self, post: ScheduledPost) -> ScheduledPost:
        stmt = select(ScheduledPostModel).where(ScheduledPostModel.id == post.id)
        result = await self._session.execute(stmt)
        existing = result.scalar_one_or_none()

        if existing is None:
            model = ScheduledPostModel(
                id=post.id,
                job_id=post.job_id,
                creator_id=post.creator_id,
                platform=post.platform,
                scheduled_date=post.scheduled_date,
                slot=post.slot.value,
                conversions_count=post.conversions_count,
                revenue_attributed_cents=post.revenue_attributed_cents,
                created_at=post.created_at,
            )
            self._session.add(model)
        else:
            existing.platform = post.platform
            existing.scheduled_date = post.scheduled_date
            existing.slot = post.slot.value
            existing.conversions_count = post.conversions_count
            existing.revenue_attributed_cents = post.revenue_attributed_cents
            model = existing

        await self._session.commit()
        return self._to_domain(model)


class PublicApiCatalogLookupAdapter(CatalogLookupPort):
    """Adapter consuming app.modules.commerce.public_api.get_product_public_info (Law 1)."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_product_info(self, product_id: UUID) -> LinkedProductInfo | None:
        try:
            dto = await get_product_public_info(
                product_id=product_id,
                session=self._session,
            )
        except ProductNotFoundError:
            return None

        return LinkedProductInfo(
            id=dto.id,
            sku=dto.sku,
            title=dto.title,
            price_cents=dto.price_cents,
            is_active=dto.is_active,
        )

    async def get_cross_sell_bundle(self, product_id: UUID) -> dict | None:
        return await get_cross_sell_recommendation_public(
            product_id=product_id,
            session=self._session,
        )


class LocalMediaArtifactGenerator(MediaArtifactGeneratorPort):
    """Generates physical .srt, .md, .json, .ics, and .mp4 files in backend/media_outputs/{job_id}/."""

    def __init__(self, base_dir: Path = MEDIA_OUTPUTS_DIR) -> None:
        self._base_dir = base_dir
        self._video_pipeline = RealVideoClipperPipeline(outputs_base_dir=base_dir)

    @staticmethod
    def _extract_yt_dlp_metadata_if_available(source_url: str) -> dict[str, str]:
        if not source_url.startswith(("http://", "https://")):
            return {}
        if "superapp.io" in source_url or "localhost" in source_url:
            return {}
        if importlib.util.find_spec("yt_dlp") is None:
            return {}

        try:
            import yt_dlp  # type: ignore[import-not-found]

            opts = {
                "quiet": True,
                "no_warnings": True,
                "skip_download": True,
                "socket_timeout": 3,
            }
            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(source_url, download=False)
                if isinstance(info, dict):
                    return {
                        "video_title": str(info.get("title") or ""),
                        "video_duration_sec": str(info.get("duration") or ""),
                        "video_thumbnail": str(info.get("thumbnail") or ""),
                    }
        except Exception:
            return {}
        return {}

    def persist_job_artifacts(
        self,
        job: MediaJob,
        payload: dict[str, str],
        enable_real_media_pipeline: bool = False,
        burn_subtitles: bool = True,
    ) -> dict[str, str]:
        job_dir = self._base_dir / str(job.id)
        job_dir.mkdir(parents=True, exist_ok=True)

        enriched = dict(payload)
        default_srt = enriched.get(
            "captions_srt_preview",
            "1\n00:00:00,000 --> 00:00:05,000\nSubtítulos generados por Super App Studio IA.\n",
        )

        # Execute RealVideoClipperPipeline (with Audio Peak Finder + TikTok subtitle burn-in)
        pipeline_meta = self._video_pipeline.execute_pipeline(
            job_id=job.id,
            source_url_or_prompt=job.source_url_or_prompt,
            enable_real_media_pipeline=enable_real_media_pipeline,
            burn_subtitles=burn_subtitles,
            default_srt_content=default_srt,
        )
        enriched.update(pipeline_meta)

        if not enable_real_media_pipeline:
            yt_meta = self._extract_yt_dlp_metadata_if_available(
                job.source_url_or_prompt
            )
            enriched.update({k: v for k, v in yt_meta.items() if v})

        srt_content = enriched.get(
            "captions_srt_preview",
            "1\n00:00:00,000 --> 00:00:05,000\nSubtítulos generados por Super App Studio IA.\n",
        )
        srt_path = job_dir / "captions.srt"
        srt_path.write_text(srt_content, encoding="utf-8")

        md_lines = [
            f"# Production Pack — {job.job_type.value} ({job.content_niche.value})",
            f"- **Job ID:** `{job.id}`",
            f"- **Nicho de Contenido:** `{job.content_niche.value}`",
            f"- **Pipeline Video:** `{enriched.get('pipeline_mode', 'synthetic_fast')}`",
            f"- **Source / Prompt:** `{job.source_url_or_prompt}`",
        ]
        if "product_title" in enriched:
            md_lines.append(
                f"- **Producto Vinculado:** {enriched['product_title']} (`{enriched.get('product_sku', '')}`)"
            )
        if "ugc_hook_0_3s" in enriched:
            md_lines.extend(
                [
                    "",
                    "## Guion TikTok / Reels (Estructura de Retención Multinicho)",
                    f"1. **Hook (0-3s):** {enriched['ugc_hook_0_3s']}",
                    f"2. **Cuerpo (3-12s):** {enriched.get('ugc_body_3_12s', '')}",
                    f"3. **CTA (12-15s):** {enriched.get('ugc_cta_12_15s', '')}",
                    "",
                    "## Mapa de Cortes CapCut (Cada 4 Segundos)",
                    f"- {enriched.get('capcut_camera_cuts', '')}",
                ]
            )
        if "weekly_plan_monday" in enriched:
            md_lines.extend(
                [
                    "",
                    "## Plan Semanal de Outfits IA",
                    f"- {enriched.get('weekly_plan_monday', '')}",
                    f"- {enriched.get('weekly_plan_tuesday', '')}",
                    f"- {enriched.get('weekly_plan_wednesday', '')}",
                    f"- {enriched.get('weekly_plan_thursday', '')}",
                    f"- {enriched.get('weekly_plan_friday', '')}",
                    f"- {enriched.get('weekly_plan_weekend', '')}",
                ]
            )
        if "cross_sell_bundle_name" in enriched:
            md_lines.extend(
                [
                    "",
                    "## 🛍️ Oferta de Venta Cruzada / Outfit Completo",
                    f"- **Combo:** {enriched['cross_sell_bundle_name']}",
                    f"- **Precio Combo:** {enriched.get('cross_sell_bundle_price', '')}",
                    f"- **Ahorro Cliente:** {enriched.get('cross_sell_bundle_savings', '')}",
                ]
            )

        md_path = job_dir / "script_tiktok.md"
        md_path.write_text("\n".join(md_lines) + "\n", encoding="utf-8")

        enriched["srt_file_path"] = str(srt_path)
        enriched["script_markdown_path"] = str(md_path)

        pack_path = job_dir / "production_pack.json"
        pack_path.write_text(
            json.dumps(enriched, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        enriched["production_pack_path"] = str(pack_path)
        return enriched

    def read_srt_content(self, job_id: UUID) -> str | None:
        srt_path = self._base_dir / str(job_id) / "captions.srt"
        if srt_path.is_file():
            return srt_path.read_text(encoding="utf-8")
        return None

    def read_script_markdown(self, job_id: UUID) -> str | None:
        md_path = self._base_dir / str(job_id) / "script_tiktok.md"
        if md_path.is_file():
            return md_path.read_text(encoding="utf-8")
        return None

    def get_mp4_file_path(self, job_id: UUID) -> str | None:
        mp4_path = self._base_dir / str(job_id) / "short_9x16.mp4"
        if not mp4_path.is_file():
            job_dir = self._base_dir / str(job_id)
            job_dir.mkdir(parents=True, exist_ok=True)
            mp4_path.write_bytes(MINIMAL_MP4_BYTES)
        return str(mp4_path)

    def persist_calendar_invite_ics(
        self,
        post: ScheduledPost,
        job: MediaJob,
    ) -> str:
        """Generates a Google Calendar compatible .ics file with a 15-minute VALARM."""
        job_dir = self._base_dir / str(job.id)
        job_dir.mkdir(parents=True, exist_ok=True)

        date_compact = post.scheduled_date.strftime("%Y%m%d")
        if post.slot == PublishingSlot.SLOT_1_MIDDAY:
            dt_start = f"{date_compact}T123000"
            dt_end = f"{date_compact}T130000"
            slot_label = "Franja 1 Mediodía (12:30)"
        else:
            dt_start = f"{date_compact}T193000"
            dt_end = f"{date_compact}T200000"
            slot_label = "Franja 2 Noche (19:30)"

        hook_preview = (
            job.result_payload.get("ugc_hook_0_3s", job.source_url_or_prompt)
            if job.result_payload
            else job.source_url_or_prompt
        )
        ics_lines = [
            "BEGIN:VCALENDAR",
            "VERSION:2.0",
            "PRODID:-//Super App Ecosystem//Media AI Publisher//ES",
            "CALSCALE:GREGORIAN",
            "METHOD:PUBLISH",
            "BEGIN:VEVENT",
            f"UID:superapp-post-{post.id}@superapp.co",
            f"DTSTART:{dt_start}",
            f"DTEND:{dt_end}",
            f"SUMMARY:[{post.platform}] Publicar Video ({slot_label}) — {job.job_type.value}",
            f"DESCRIPTION:Job ID: {job.id} | Hook: {hook_preview}",
            "BEGIN:VALARM",
            "TRIGGER:-PT15M",
            "ACTION:DISPLAY",
            "DESCRIPTION:Recordatorio Super App: Publicar video en 15 minutos",
            "END:VALARM",
            "END:VEVENT",
            "END:VCALENDAR",
        ]
        ics_path = job_dir / "calendar_invite.ics"
        ics_path.write_text("\r\n".join(ics_lines) + "\r\n", encoding="utf-8")
        return str(ics_path)

    PURGEABLE_ARTIFACT_FILENAMES: tuple[str, ...] = (
        "source_720p.mp4",
        "short_9x16.mp4",
        "captions.srt",
        "production_pack.json",
    )

    def read_ics_content(self, job_id: UUID) -> str | None:
        ics_path = self._base_dir / str(job_id) / "calendar_invite.ics"
        if ics_path.is_file():
            return ics_path.read_text(encoding="utf-8")
        return None

    def purge_job_artifacts(self, job_id: UUID) -> tuple[int, int]:
        """Physically deletes heavy temporary artifacts for job_id, returning (files_deleted, bytes_reclaimed)."""
        job_dir = self._base_dir / str(job_id)
        if not job_dir.is_dir():
            return 0, 0

        files_deleted = 0
        bytes_reclaimed = 0
        for filename in self.PURGEABLE_ARTIFACT_FILENAMES:
            file_path = job_dir / filename
            if file_path.is_file():
                bytes_reclaimed += file_path.stat().st_size
                file_path.unlink()
                files_deleted += 1

        return files_deleted, bytes_reclaimed


artifact_generator = LocalMediaArtifactGenerator()


class BackgroundTaskJobDispatcher(AsyncJobDispatcherPort):
    """Schedules heavy Media AI execution outside the HTTP cycle with its own DB session (Law 5)."""

    def __init__(self) -> None:
        self._tasks: set[asyncio.Task[None]] = set()

    async def _run_job_in_background(self, job_id: UUID) -> None:
        await asyncio.sleep(0.05)
        session_factory = get_session_factory()
        async with session_factory() as session:
            repository = SqlAlchemyMediaJobRepository(session)
            catalog_lookup = PublicApiCatalogLookupAdapter(session)
            use_case = ExecuteMediaJobUseCase(
                repository=repository,
                catalog_lookup=catalog_lookup,
                event_bus=event_bus,
                artifact_generator=artifact_generator,
            )
            await use_case.execute(job_id=job_id)

    def dispatch(self, job_id: UUID) -> None:
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            return
        task = loop.create_task(self._run_job_in_background(job_id))
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)


job_dispatcher = BackgroundTaskJobDispatcher()
