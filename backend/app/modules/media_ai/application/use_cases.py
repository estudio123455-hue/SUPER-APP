"""Application Use Cases for the Media AI bounded context (Layer 2)."""

from datetime import UTC, date, datetime, timedelta
from uuid import UUID

from app.core.event_bus import InMemoryEventBus
from app.modules.media_ai.application.dtos import (
    CleanupExpiredMediaArtifactsResultDTO,
    DailyStreakProgressDTO,
    EnqueueMediaJobCommand,
    MediaJobDTO,
    NichePerformanceAnalyticsDTO,
    NichePerformanceMetricDTO,
    ScheduledPostDTO,
    ScheduleMediaPostCommand,
)
from app.modules.media_ai.application.events import (
    MediaJobCompletedEvent,
    MediaJobQueuedEvent,
)
from app.modules.media_ai.domain.entities import (
    ContentNiche,
    JobStatus,
    JobType,
    MediaJob,
    ScheduledPost,
)
from app.modules.media_ai.domain.exceptions import (
    LinkedProductNotFoundError,
    MediaJobNotFoundError,
    SlotAlreadyBookedError,
)
from app.modules.media_ai.domain.repositories import (
    AsyncJobDispatcherPort,
    CatalogLookupPort,
    LinkedProductInfo,
    MediaArtifactGeneratorPort,
    MediaJobRepository,
    ScheduledPostRepository,
)


class EnqueueMediaJobUseCase:
    """Validates linked product (if any), persists QUEUED MediaJob, and dispatches async work."""

    def __init__(
        self,
        repository: MediaJobRepository,
        catalog_lookup: CatalogLookupPort,
        dispatcher: AsyncJobDispatcherPort,
        event_bus: InMemoryEventBus,
    ) -> None:
        self._repository = repository
        self._catalog_lookup = catalog_lookup
        self._dispatcher = dispatcher
        self._event_bus = event_bus

    async def execute(self, command: EnqueueMediaJobCommand) -> MediaJobDTO:
        if command.linked_product_id is not None:
            product_info = await self._catalog_lookup.get_product_info(
                command.linked_product_id
            )
            if product_info is None or not product_info.is_active:
                raise LinkedProductNotFoundError(str(command.linked_product_id))

        job = MediaJob(
            creator_id=command.creator_id,
            job_type=command.job_type,
            content_niche=command.content_niche,
            source_url_or_prompt=command.source_url_or_prompt,
            linked_product_id=command.linked_product_id,
            use_real_pipeline=command.use_real_pipeline,
            burn_subtitles=command.burn_subtitles,
            status=JobStatus.QUEUED,
            progress_percent=0,
        )
        saved_job = await self._repository.save(job)

        await self._event_bus.publish(
            MediaJobQueuedEvent(
                job_id=saved_job.id,
                creator_id=saved_job.creator_id,
                job_type=saved_job.job_type.value,
                linked_product_id=saved_job.linked_product_id,
            )
        )

        # Law 5: Heavy work is scheduled off the HTTP main thread
        self._dispatcher.dispatch(saved_job.id)

        return MediaJobDTO.from_entity(saved_job)


class ExecuteMediaJobUseCase:
    """Background worker use case that processes a MediaJob, writes real artifacts, and completes it."""

    def __init__(
        self,
        repository: MediaJobRepository,
        catalog_lookup: CatalogLookupPort,
        event_bus: InMemoryEventBus,
        artifact_generator: MediaArtifactGeneratorPort | None = None,
    ) -> None:
        self._repository = repository
        self._catalog_lookup = catalog_lookup
        self._event_bus = event_bus
        self._artifact_generator = artifact_generator

    @staticmethod
    def _build_niche_retention_blocks(
        niche: ContentNiche,
        product_label: str,
        price_cop: str,
        source_prompt: str,
    ) -> tuple[str, str, str, str]:
        if niche == ContentNiche.RAP_CULTURE_VIRAL:
            hook = f"[Beat Drop 0-3s] El detalle oculto en la barra que nadie notó: {source_prompt}"
            body = (
                f"[Corte cada 4s + Zoom Punch] Analizamos el flow, el contexto de calle y "
                f"el look oficial con {product_label}."
            )
            cta = f"[12-15s] Consigue {product_label} hoy por {price_cop} con Billetera o Contraentrega."
            cuts = "00s-04s: Close-up Reacción | 04s-08s: B-Roll Letra Resaltada | 08s-12s: Toma Producto | 12s-15s: CTA"
            return hook, body, cta, cuts

        if niche == ContentNiche.YOUTUBE_HIGHLIGHT_CLIP:
            hook = f"[0-3s Subtítulo Explosivo] El momento más tenso del stream: '{source_prompt}'"
            body = (
                f"[4s-12s Split-Screen 9:16] Cámara arriba con reacción + gameplay/setup abajo "
                f"mostrando {product_label} en acción."
            )
            cta = f"[12-15s] Link directo a {product_label} ({price_cop}) en el perfil."
            cuts = "00s-04s: Hook Zoom 130% | 04s-08s: Split Screen | 08s-12s: Replay Slow-Mo | 12s-15s: Overlay Compra"
            return hook, body, cta, cuts

        if niche == ContentNiche.MENSWEAR_LOOKBOOK:
            hook = f"[0-3s Transición Snap] 3 combinaciones urbanas para dominar la semana con {product_label}."
            body = (
                f"[4s-12s Cortes al ritmo del bajo] Silueta oversize, caída limpia y textura impermeable "
                f"lista para el clima de Bogotá."
            )
            cta = f"[12-15s] Estrena {product_label} por {price_cop} — envío rápido y Pago Contraentrega."
            cuts = "00s-04s: Plano Entero Fit | 04s-08s: Macro Textura/Bordado | 08s-12s: Caminata Nocturna | 12s-15s: CTA"
            return hook, body, cta, cuts

        # Default: DESK_SETUP_UGC
        hook = f"¿Dolor de cuello y ojos cansados al trabajar? Mira cómo cambia tu escritorio con {product_label}."
        body = (
            f"Instalamos {product_label} en 10 segundos: luz asimétrica sin reflejos en pantalla "
            f"y postura ergonómica real."
        )
        cta = f"Pídelo hoy por {price_cop} con Billetera Super App o Pago Contraentrega en toda Colombia."
        cuts = "00s-04s: POV Escritorio Oscuro | 04s-08s: Unboxing Rápido | 08s-12s: Encendido LED + Soporte | 12s-15s: CTA"
        return hook, body, cta, cuts

    @classmethod
    def _build_enriched_payload(
        cls,
        job: MediaJob,
        product_info: LinkedProductInfo | None,
    ) -> dict[str, str]:
        product_label = (
            product_info.title
            if product_info is not None
            else "Combo Setup Ergonómico Super App"
        )
        price_cop = (
            f"${product_info.price_cents // 100:,} COP"
            if product_info is not None
            else "$95,000 COP"
        )

        hook, body, cta, cuts = cls._build_niche_retention_blocks(
            niche=job.content_niche,
            product_label=product_label,
            price_cop=price_cop,
            source_prompt=job.source_url_or_prompt,
        )

        payload: dict[str, str] = {
            "engine": "superapp-media-ai-v1",
            "job_type": job.job_type.value,
            "content_niche": job.content_niche.value,
            "source": job.source_url_or_prompt,
            "srt_download_url": f"/api/v1/media-ai/jobs/{job.id}/download-srt",
            "pack_download_url": f"/api/v1/media-ai/jobs/{job.id}/download-pack",
            "mp4_download_url": f"/api/v1/media-ai/jobs/{job.id}/download-mp4",
            "capcut_camera_cuts": cuts,
            "ugc_hook_0_3s": hook,
            "ugc_body_3_12s": body,
            "ugc_cta_12_15s": cta,
        }

        if job.job_type in {JobType.VIRAL_SHORT_CLIP, JobType.PRODUCT_SHOWCASE_VIDEO}:
            folder = (
                "clips"
                if job.job_type == JobType.VIRAL_SHORT_CLIP
                else "showcase"
            )
            payload["output_video_url"] = (
                f"https://cdn.superapp.io/{folder}/{job.id}/reel_9x16.mp4"
            )
            payload["aspect_ratio"] = "9:16"
            payload["cta_overlay"] = "enabled"
            payload["captions_srt_preview"] = (
                "1\n00:00:00,000 --> 00:00:03,000\n"
                f"{hook}\n\n"
                "2\n00:00:03,000 --> 00:00:12,000\n"
                f"{body}\n\n"
                "3\n00:00:12,000 --> 00:00:15,000\n"
                f"{cta}\n"
            )
        elif job.job_type == JobType.AUTO_CAPTIONS_WHISPER:
            payload["subtitles_srt_url"] = (
                f"https://cdn.superapp.io/captions/{job.id}/es_CO.srt"
            )
            payload["detected_language"] = "es"
            payload["captions_srt_preview"] = (
                "1\n00:00:00,000 --> 00:00:04,000\n"
                f"{hook}\n\n"
                "2\n00:00:04,000 --> 00:00:10,000\n"
                f"{body}\n"
            )
        elif job.job_type == JobType.AI_OUTFIT_RECOMMENDATION:
            payload["recommended_style"] = "Urban Techwear Capsule"
            payload["confidence_score"] = "0.96"
            payload["weekly_plan_monday"] = (
                "Lunes: Chaqueta Oversize RBR Edition + Cargo Negro + Sneakers Blancos"
            )
            payload["weekly_plan_tuesday"] = (
                "Martes: Hoodie Gris Minimal + Jeans Rectos + Botas Urbanas"
            )
            payload["weekly_plan_wednesday"] = (
                "Miércoles: Camiseta Heavyweight Blanca + Chaqueta Oversize RBR Edition"
            )
            payload["weekly_plan_thursday"] = (
                "Jueves: Look Smart-Casual Oficina Creativa + Accesorios Negros"
            )
            payload["weekly_plan_friday"] = (
                "Viernes Nocturno: Total Black + Chaqueta Oversize RBR Edition"
            )
            payload["weekly_plan_weekend"] = (
                "Sábado & Domingo: Athleisure Cómodo + Gorra Estructurada"
            )
            payload["captions_srt_preview"] = (
                "1\n00:00:00,000 --> 00:00:03,500\n"
                f"{payload['weekly_plan_monday']}\n\n"
                "2\n00:00:03,500 --> 00:00:07,000\n"
                f"{payload['weekly_plan_wednesday']}\n\n"
                "3\n00:00:07,000 --> 00:00:10,500\n"
                f"{payload['weekly_plan_friday']}\n"
            )

        if product_info is not None:
            payload["linked_product_id"] = str(product_info.id)
            payload["product_sku"] = product_info.sku
            payload["product_title"] = product_info.title
            payload["product_price_cents"] = str(product_info.price_cents)

        return payload

    async def execute(self, job_id: UUID) -> MediaJobDTO:
        job = await self._repository.get_by_id(job_id)
        if job is None:
            raise MediaJobNotFoundError(str(job_id))

        if job.status == JobStatus.COMPLETED:
            return MediaJobDTO.from_entity(job)

        processing_job = job.mark_processing(progress=50)
        await self._repository.save(processing_job)

        product_info: LinkedProductInfo | None = None
        cross_sell_bundle: dict | None = None
        if job.linked_product_id is not None:
            product_info = await self._catalog_lookup.get_product_info(
                job.linked_product_id
            )
            if hasattr(self._catalog_lookup, "get_cross_sell_bundle"):
                cross_sell_bundle = await self._catalog_lookup.get_cross_sell_bundle(
                    job.linked_product_id
                )

        payload = self._build_enriched_payload(processing_job, product_info)
        if cross_sell_bundle is not None:
            payload["cross_sell_bundle_name"] = str(cross_sell_bundle["bundle_name"])
            payload["cross_sell_bundle_price"] = (
                f"${cross_sell_bundle['bundle_price_cents'] // 100:,} COP"
            )
            payload["cross_sell_bundle_savings"] = (
                f"${cross_sell_bundle['savings_cents'] // 100:,} COP"
            )
            payload["cross_sell_complement_id"] = str(
                cross_sell_bundle["complement_product_id"]
            )
            payload["cross_sell_complement_sku"] = str(
                cross_sell_bundle["complement_sku"]
            )
            payload["cross_sell_complement_title"] = str(
                cross_sell_bundle["complement_title"]
            )
            payload["cross_sell_bundle_price_cents"] = str(
                cross_sell_bundle["bundle_price_cents"]
            )
            payload["cross_sell_savings_cents"] = str(
                cross_sell_bundle["savings_cents"]
            )
            payload["cross_sell_discount_percentage"] = str(
                cross_sell_bundle["discount_percentage"]
            )
        if self._artifact_generator is not None:
            payload = self._artifact_generator.persist_job_artifacts(
                processing_job,
                payload,
                enable_real_media_pipeline=processing_job.use_real_pipeline,
                burn_subtitles=processing_job.burn_subtitles,
            )

        completed_job = processing_job.mark_completed(payload)
        saved_completed = await self._repository.save(completed_job)

        await self._event_bus.publish(
            MediaJobCompletedEvent(
                job_id=saved_completed.id,
                creator_id=saved_completed.creator_id,
                job_type=saved_completed.job_type.value,
                linked_product_id=saved_completed.linked_product_id,
                result_payload=payload,
            )
        )

        return MediaJobDTO.from_entity(saved_completed)


class GetMediaJobUseCase:
    """Retrieves a single MediaJob by ID."""

    def __init__(self, repository: MediaJobRepository) -> None:
        self._repository = repository

    async def execute(self, job_id: UUID) -> MediaJobDTO:
        job = await self._repository.get_by_id(job_id)
        if job is None:
            raise MediaJobNotFoundError(str(job_id))
        return MediaJobDTO.from_entity(job)


class ListCreatorJobsUseCase:
    """Lists all MediaJobs belonging to a creator."""

    def __init__(self, repository: MediaJobRepository) -> None:
        self._repository = repository

    async def execute(self, creator_id: UUID) -> list[MediaJobDTO]:
        jobs = await self._repository.list_by_creator(creator_id)
        return [MediaJobDTO.from_entity(j) for j in jobs]


class ScheduleMediaPostUseCase:
    """Schedules a MediaJob into SLOT_1_MIDDAY or SLOT_2_EVENING and generates calendar_invite.ics."""

    def __init__(
        self,
        job_repository: MediaJobRepository,
        post_repository: ScheduledPostRepository,
        artifact_generator: MediaArtifactGeneratorPort | None = None,
    ) -> None:
        self._job_repository = job_repository
        self._post_repository = post_repository
        self._artifact_generator = artifact_generator

    async def execute(self, command: ScheduleMediaPostCommand) -> ScheduledPostDTO:
        job = await self._job_repository.get_by_id(command.job_id)
        if job is None:
            raise MediaJobNotFoundError(str(command.job_id))

        existing_slot = await self._post_repository.get_by_date_and_slot(
            creator_id=command.creator_id,
            scheduled_date=command.scheduled_date,
            slot=command.slot,
        )
        if existing_slot is not None and existing_slot.job_id != command.job_id:
            raise SlotAlreadyBookedError(
                scheduled_date=command.scheduled_date.isoformat(),
                slot=command.slot.value,
            )

        existing_for_job = await self._post_repository.get_by_job_id(command.job_id)
        if existing_for_job is not None:
            post = ScheduledPost(
                id=existing_for_job.id,
                job_id=command.job_id,
                creator_id=command.creator_id,
                platform=command.platform,
                scheduled_date=command.scheduled_date,
                slot=command.slot,
                conversions_count=existing_for_job.conversions_count,
                revenue_attributed_cents=existing_for_job.revenue_attributed_cents,
                created_at=existing_for_job.created_at,
            )
        else:
            post = ScheduledPost(
                job_id=command.job_id,
                creator_id=command.creator_id,
                platform=command.platform,
                scheduled_date=command.scheduled_date,
                slot=command.slot,
            )

        saved_post = await self._post_repository.save(post)
        if self._artifact_generator is not None:
            self._artifact_generator.persist_calendar_invite_ics(saved_post, job)

        return ScheduledPostDTO.from_entity(saved_post)


class GetDailyStreakProgressUseCase:
    """Calculates the 2-videos/day publishing goal progress and lists scheduled posts."""

    DAILY_GOAL = 2

    def __init__(self, post_repository: ScheduledPostRepository) -> None:
        self._post_repository = post_repository

    async def execute(
        self,
        creator_id: UUID,
        target_date: date | None = None,
    ) -> DailyStreakProgressDTO:
        effective_date = target_date or datetime.now(UTC).date()
        posts = await self._post_repository.list_by_creator(creator_id)
        today_count = sum(1 for p in posts if p.scheduled_date == effective_date)
        total_conversions = sum(p.conversions_count for p in posts)
        total_revenue = sum(p.revenue_attributed_cents for p in posts)

        return DailyStreakProgressDTO(
            target_date=effective_date,
            scheduled_today_count=today_count,
            daily_goal=self.DAILY_GOAL,
            goal_completed=today_count >= self.DAILY_GOAL,
            total_conversions=total_conversions,
            total_revenue_attributed_cents=total_revenue,
            scheduled_posts=tuple(ScheduledPostDTO.from_entity(p) for p in posts),
        )


class RecordVideoConversionUseCase:
    """Increments conversions_count and revenue_attributed_cents when an order attributes a video."""

    def __init__(
        self,
        job_repository: MediaJobRepository,
        post_repository: ScheduledPostRepository,
    ) -> None:
        self._job_repository = job_repository
        self._post_repository = post_repository

    async def execute(
        self,
        source_job_id: UUID,
        order_total_cents: int,
    ) -> ScheduledPostDTO | None:
        post = await self._post_repository.get_by_job_id(source_job_id)
        if post is None:
            job = await self._job_repository.get_by_id(source_job_id)
            if job is None:
                return None
            from app.modules.media_ai.domain.entities import PublishingSlot

            post = ScheduledPost(
                job_id=job.id,
                creator_id=job.creator_id,
                platform="TIKTOK",
                scheduled_date=datetime.now(UTC).date(),
                slot=PublishingSlot.SLOT_1_MIDDAY,
            )

        updated_post = post.record_conversion(order_total_cents)
        saved = await self._post_repository.save(updated_post)
        return ScheduledPostDTO.from_entity(saved)


class GetNichePerformanceAnalyticsUseCase:
    """Aggregates MediaJobs and ScheduledPosts by ContentNiche to compute content ROI."""

    def __init__(
        self,
        job_repository: MediaJobRepository,
        post_repository: ScheduledPostRepository,
    ) -> None:
        self._job_repository = job_repository
        self._post_repository = post_repository

    async def execute(self, creator_id: UUID) -> NichePerformanceAnalyticsDTO:
        jobs = await self._job_repository.list_by_creator(creator_id)
        posts = await self._post_repository.list_by_creator(creator_id)

        post_by_job_id: dict[UUID, ScheduledPost] = {p.job_id: p for p in posts}

        metrics_by_niche: dict[ContentNiche, dict[str, int]] = {
            niche: {
                "created": 0,
                "scheduled": 0,
                "conversions": 0,
                "revenue_cents": 0,
            }
            for niche in ContentNiche
        }

        for job in jobs:
            bucket = metrics_by_niche[job.content_niche]
            bucket["created"] += 1
            post = post_by_job_id.get(job.id)
            if post is not None:
                bucket["scheduled"] += 1
                bucket["conversions"] += post.conversions_count
                bucket["revenue_cents"] += post.revenue_attributed_cents

        niche_dtos: list[NichePerformanceMetricDTO] = []
        top_niche: ContentNiche | None = None
        top_revenue = 0

        for niche in ContentNiche:
            bucket = metrics_by_niche[niche]
            created_count = bucket["created"]
            conversions = bucket["conversions"]
            revenue = bucket["revenue_cents"]
            conv_rate = (
                round(conversions / created_count, 2) if created_count > 0 else 0.0
            )
            if revenue > top_revenue:
                top_revenue = revenue
                top_niche = niche

            niche_dtos.append(
                NichePerformanceMetricDTO(
                    content_niche=niche,
                    total_videos_created=created_count,
                    total_videos_scheduled=bucket["scheduled"],
                    conversions_count=conversions,
                    revenue_attributed_cents=revenue,
                    conversions_per_video=conv_rate,
                )
            )

        return NichePerformanceAnalyticsDTO(
            top_performing_niche=top_niche,
            total_videos_created=sum(m.total_videos_created for m in niche_dtos),
            total_videos_scheduled=sum(m.total_videos_scheduled for m in niche_dtos),
            total_conversions=sum(m.conversions_count for m in niche_dtos),
            total_revenue_attributed_cents=sum(
                m.revenue_attributed_cents for m in niche_dtos
            ),
            niches=tuple(niche_dtos),
        )


class CleanupExpiredMediaArtifactsUseCase:
    """Purges heavy disk artifacts from expired terminal MediaJobs while preserving ROI metrics."""

    def __init__(
        self,
        job_repository: MediaJobRepository,
        artifact_generator: MediaArtifactGeneratorPort,
        post_repository: ScheduledPostRepository | None = None,
    ) -> None:
        self._job_repository = job_repository
        self._artifact_generator = artifact_generator
        self._post_repository = post_repository

    async def execute(
        self,
        retention_days: int = 30,
        creator_id: UUID | None = None,
        now: datetime | None = None,
    ) -> CleanupExpiredMediaArtifactsResultDTO:
        if retention_days < 0:
            raise ValueError("retention_days must be non-negative (>= 0).")

        reference_now = now or datetime.now(UTC)
        if reference_now.tzinfo is None:
            reference_now = reference_now.replace(tzinfo=UTC)
        cutoff = reference_now - timedelta(days=retention_days)

        expired_jobs = await self._job_repository.list_expired_terminal_jobs(
            cutoff=cutoff,
            creator_id=creator_id,
        )

        jobs_scanned = len(expired_jobs)
        files_deleted = 0
        bytes_reclaimed = 0
        retained_metrics_count = 0

        for job in expired_jobs:
            retained_metrics_count += 1
            if not job.artifacts_purged:
                deleted, reclaimed = self._artifact_generator.purge_job_artifacts(
                    job.id
                )
                files_deleted += deleted
                bytes_reclaimed += reclaimed
                purged_job = job.mark_artifacts_purged()
                await self._job_repository.save(purged_job)

        return CleanupExpiredMediaArtifactsResultDTO(
            retention_days=retention_days,
            jobs_scanned=jobs_scanned,
            files_deleted=files_deleted,
            bytes_reclaimed=bytes_reclaimed,
            retained_metrics_count=retained_metrics_count,
        )
