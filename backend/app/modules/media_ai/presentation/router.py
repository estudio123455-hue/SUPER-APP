"""FastAPI router for the Media AI bounded context (/api/v1/media-ai)."""

from datetime import date
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Body, Depends, HTTPException, Query, status
from fastapi.responses import FileResponse, PlainTextResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db_session
from app.core.event_bus import event_bus
from app.modules.identity.public_api import UserPublicDTO, get_current_user
from app.modules.media_ai.application.dtos import (
    EnqueueMediaJobCommand,
    ScheduleMediaPostCommand,
)
from app.modules.media_ai.application.use_cases import (
    CleanupExpiredMediaArtifactsUseCase,
    EnqueueMediaJobUseCase,
    ExecuteMediaJobUseCase,
    GetDailyStreakProgressUseCase,
    GetMediaJobUseCase,
    GetNichePerformanceAnalyticsUseCase,
    ListCreatorJobsUseCase,
    ScheduleMediaPostUseCase,
)
from app.modules.media_ai.domain.exceptions import (
    InvalidJobStateTransitionError,
    InvalidMediaSourceError,
    LinkedProductNotFoundError,
    MediaJobNotFoundError,
    SlotAlreadyBookedError,
)
from app.modules.media_ai.infrastructure.repositories import (
    PublicApiCatalogLookupAdapter,
    SqlAlchemyMediaJobRepository,
    SqlAlchemyScheduledPostRepository,
    artifact_generator,
    job_dispatcher,
)
from app.modules.media_ai.presentation.schemas import (
    DailyStreakProgressResponse,
    EnqueueMediaJobRequest,
    MediaArtifactCleanupRequest,
    MediaArtifactCleanupResponse,
    MediaJobResponse,
    NichePerformanceAnalyticsResponse,
    NichePerformanceMetricResponse,
    ScheduledPostResponse,
    ScheduleMediaPostRequest,
)

router = APIRouter(prefix="/api/v1/media-ai", tags=["Media AI"])


@router.post(
    "/jobs",
    response_model=MediaJobResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def enqueue_media_job(
    payload: EnqueueMediaJobRequest,
    current_user: Annotated[UserPublicDTO, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> MediaJobResponse:
    """Enqueues a heavy video/AI job off the main HTTP thread and returns 202 Accepted (Law 5)."""
    repository = SqlAlchemyMediaJobRepository(session)
    catalog_lookup = PublicApiCatalogLookupAdapter(session)
    use_case = EnqueueMediaJobUseCase(
        repository=repository,
        catalog_lookup=catalog_lookup,
        dispatcher=job_dispatcher,
        event_bus=event_bus,
    )

    try:
        job_dto = await use_case.execute(
            EnqueueMediaJobCommand(
                creator_id=current_user.id,
                job_type=payload.job_type,
                content_niche=payload.content_niche,
                source_url_or_prompt=payload.source_url_or_prompt,
                linked_product_id=payload.linked_product_id,
                use_real_pipeline=payload.use_real_pipeline,
                burn_subtitles=payload.burn_subtitles,
            )
        )
    except LinkedProductNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except InvalidMediaSourceError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc

    return MediaJobResponse.model_validate(job_dto)


@router.get(
    "/jobs",
    response_model=list[MediaJobResponse],
    status_code=status.HTTP_200_OK,
)
async def list_my_jobs(
    current_user: Annotated[UserPublicDTO, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> list[MediaJobResponse]:
    """Lists all MediaJobs created by the authenticated user."""
    repository = SqlAlchemyMediaJobRepository(session)
    use_case = ListCreatorJobsUseCase(repository=repository)
    jobs = await use_case.execute(creator_id=current_user.id)
    return [MediaJobResponse.model_validate(j) for j in jobs]


@router.get(
    "/jobs/{job_id}",
    response_model=MediaJobResponse,
    status_code=status.HTTP_200_OK,
)
async def get_media_job(
    job_id: UUID,
    _current_user: Annotated[UserPublicDTO, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> MediaJobResponse:
    """Retrieves the status, progress_percent, and result_payload of a MediaJob."""
    repository = SqlAlchemyMediaJobRepository(session)
    use_case = GetMediaJobUseCase(repository=repository)

    try:
        job_dto = await use_case.execute(job_id=job_id)
    except MediaJobNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc

    return MediaJobResponse.model_validate(job_dto)


@router.post(
    "/jobs/{job_id}/process-sync",
    response_model=MediaJobResponse,
    status_code=status.HTTP_200_OK,
)
async def process_media_job_sync(
    job_id: UUID,
    _current_user: Annotated[UserPublicDTO, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> MediaJobResponse:
    """Deterministically executes the worker pipeline and writes physical artifacts on disk."""
    repository = SqlAlchemyMediaJobRepository(session)
    catalog_lookup = PublicApiCatalogLookupAdapter(session)
    use_case = ExecuteMediaJobUseCase(
        repository=repository,
        catalog_lookup=catalog_lookup,
        event_bus=event_bus,
        artifact_generator=artifact_generator,
    )

    try:
        job_dto = await use_case.execute(job_id=job_id)
    except MediaJobNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except InvalidJobStateTransitionError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc

    return MediaJobResponse.model_validate(job_dto)


@router.get(
    "/jobs/{job_id}/download-srt",
    response_class=PlainTextResponse,
    status_code=status.HTTP_200_OK,
)
async def download_job_srt(
    job_id: UUID,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> PlainTextResponse:
    """Downloads the generated CapCut-ready .srt subtitle file for a completed MediaJob."""
    repository = SqlAlchemyMediaJobRepository(session)
    use_case = GetMediaJobUseCase(repository=repository)

    try:
        job_dto = await use_case.execute(job_id=job_id)
    except MediaJobNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc

    srt_content = artifact_generator.read_srt_content(job_id)
    if srt_content is None and job_dto.result_payload:
        srt_content = job_dto.result_payload.get("captions_srt_preview")

    if not srt_content:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="SRT subtitles have not been generated for this job yet.",
        )

    return PlainTextResponse(
        content=srt_content,
        media_type="application/x-subrip",
        headers={
            "Content-Disposition": f'attachment; filename="captions_{job_id}.srt"'
        },
    )


@router.get(
    "/jobs/{job_id}/download-pack",
    response_class=PlainTextResponse,
    status_code=status.HTTP_200_OK,
)
async def download_job_production_pack(
    job_id: UUID,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> PlainTextResponse:
    """Downloads the generated Markdown production guide (script_tiktok.md) for a completed job."""
    repository = SqlAlchemyMediaJobRepository(session)
    use_case = GetMediaJobUseCase(repository=repository)

    try:
        job_dto = await use_case.execute(job_id=job_id)
    except MediaJobNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc

    md_content = artifact_generator.read_script_markdown(job_id)
    if md_content is None and job_dto.result_payload:
        md_content = (
            f"# Production Pack — {job_dto.job_type.value} ({job_dto.content_niche.value})\n"
            f"- Hook: {job_dto.result_payload.get('ugc_hook_0_3s', '')}\n"
            f"- Body: {job_dto.result_payload.get('ugc_body_3_12s', '')}\n"
            f"- CTA: {job_dto.result_payload.get('ugc_cta_12_15s', '')}\n"
        )

    if not md_content:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Production pack has not been generated for this job yet.",
        )

    return PlainTextResponse(
        content=md_content,
        media_type="text/markdown",
        headers={
            "Content-Disposition": f'attachment; filename="script_{job_id}.md"'
        },
    )


@router.get(
    "/jobs/{job_id}/download-mp4",
    response_class=FileResponse,
    status_code=status.HTTP_200_OK,
)
async def download_job_vertical_mp4(
    job_id: UUID,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> FileResponse:
    """Downloads the generated vertical 9:16 short_9x16.mp4 clip for a completed MediaJob."""
    repository = SqlAlchemyMediaJobRepository(session)
    use_case = GetMediaJobUseCase(repository=repository)

    try:
        await use_case.execute(job_id=job_id)
    except MediaJobNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc

    mp4_path = artifact_generator.get_mp4_file_path(job_id)
    if not mp4_path:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Vertical MP4 clip has not been generated for this job yet.",
        )

    return FileResponse(
        path=mp4_path,
        media_type="video/mp4",
        filename=f"short_9x16_{job_id}.mp4",
    )


@router.post(
    "/jobs/{job_id}/schedule",
    response_model=ScheduledPostResponse,
    status_code=status.HTTP_201_CREATED,
)
async def schedule_media_post(
    job_id: UUID,
    payload: ScheduleMediaPostRequest,
    current_user: Annotated[UserPublicDTO, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> ScheduledPostResponse:
    """Schedules a MediaJob into SLOT_1_MIDDAY or SLOT_2_EVENING and generates calendar_invite.ics."""
    job_repo = SqlAlchemyMediaJobRepository(session)
    post_repo = SqlAlchemyScheduledPostRepository(session)
    use_case = ScheduleMediaPostUseCase(
        job_repository=job_repo,
        post_repository=post_repo,
        artifact_generator=artifact_generator,
    )

    try:
        post_dto = await use_case.execute(
            ScheduleMediaPostCommand(
                job_id=job_id,
                creator_id=current_user.id,
                platform=payload.platform,
                scheduled_date=payload.scheduled_date,
                slot=payload.slot,
            )
        )
    except MediaJobNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except SlotAlreadyBookedError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc

    return ScheduledPostResponse.model_validate(post_dto)


@router.get(
    "/schedule",
    response_model=DailyStreakProgressResponse,
    status_code=status.HTTP_200_OK,
)
async def get_publishing_schedule(
    current_user: Annotated[UserPublicDTO, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
    target_date: date | None = None,
) -> DailyStreakProgressResponse:
    """Returns the creator's scheduled posts and 2-videos/day goal progress."""
    post_repo = SqlAlchemyScheduledPostRepository(session)
    use_case = GetDailyStreakProgressUseCase(post_repository=post_repo)
    dto = await use_case.execute(
        creator_id=current_user.id,
        target_date=target_date,
    )
    return DailyStreakProgressResponse(
        target_date=dto.target_date,
        scheduled_today_count=dto.scheduled_today_count,
        daily_goal=dto.daily_goal,
        goal_completed=dto.goal_completed,
        total_conversions=dto.total_conversions,
        total_revenue_attributed_cents=dto.total_revenue_attributed_cents,
        scheduled_posts=[
            ScheduledPostResponse.model_validate(p) for p in dto.scheduled_posts
        ],
    )


@router.get(
    "/jobs/{job_id}/download-ics",
    response_class=PlainTextResponse,
    status_code=status.HTTP_200_OK,
)
async def download_job_calendar_ics(
    job_id: UUID,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> PlainTextResponse:
    """Downloads the Google Calendar .ics invite with 15-minute VALARM reminder."""
    job_repo = SqlAlchemyMediaJobRepository(session)
    post_repo = SqlAlchemyScheduledPostRepository(session)
    job = await job_repo.get_by_id(job_id)
    if job is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"MediaJob '{job_id}' was not found.",
        )

    ics_content = artifact_generator.read_ics_content(job_id)
    if ics_content is None:
        post = await post_repo.get_by_job_id(job_id)
        if post is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="This job has not been scheduled yet.",
            )
        artifact_generator.persist_calendar_invite_ics(post, job)
        ics_content = artifact_generator.read_ics_content(job_id)

    return PlainTextResponse(
        content=ics_content or "",
        media_type="text/calendar",
        headers={
            "Content-Disposition": f'attachment; filename="publish_{job_id}.ics"'
        },
    )


@router.get(
    "/analytics/by-niche",
    response_model=NichePerformanceAnalyticsResponse,
    status_code=status.HTTP_200_OK,
)
async def get_niche_performance_analytics(
    current_user: Annotated[UserPublicDTO, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> NichePerformanceAnalyticsResponse:
    """Returns ROI and conversion performance grouped by ContentNiche."""
    job_repo = SqlAlchemyMediaJobRepository(session)
    post_repo = SqlAlchemyScheduledPostRepository(session)
    use_case = GetNichePerformanceAnalyticsUseCase(
        job_repository=job_repo,
        post_repository=post_repo,
    )
    dto = await use_case.execute(creator_id=current_user.id)
    return NichePerformanceAnalyticsResponse(
        top_performing_niche=dto.top_performing_niche,
        total_videos_created=dto.total_videos_created,
        total_videos_scheduled=dto.total_videos_scheduled,
        total_conversions=dto.total_conversions,
        total_revenue_attributed_cents=dto.total_revenue_attributed_cents,
        niches=[
            NichePerformanceMetricResponse.model_validate(n) for n in dto.niches
        ],
    )


@router.post(
    "/maintenance/cleanup",
    response_model=MediaArtifactCleanupResponse,
    status_code=status.HTTP_200_OK,
)
async def cleanup_expired_media_artifacts(
    current_user: Annotated[UserPublicDTO, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
    retention_days: Annotated[int | None, Query(ge=0, le=3650)] = None,
    payload: MediaArtifactCleanupRequest | None = Body(default=None),
) -> MediaArtifactCleanupResponse:
    """Purges heavy physical media artifacts older than retention_days while preserving ROI metrics."""
    effective_retention_days = (
        retention_days
        if retention_days is not None
        else (payload.retention_days if payload is not None else 30)
    )
    job_repo = SqlAlchemyMediaJobRepository(session)
    post_repo = SqlAlchemyScheduledPostRepository(session)
    use_case = CleanupExpiredMediaArtifactsUseCase(
        job_repository=job_repo,
        artifact_generator=artifact_generator,
        post_repository=post_repo,
    )
    result_dto = await use_case.execute(
        retention_days=effective_retention_days,
        creator_id=current_user.id,
    )
    return MediaArtifactCleanupResponse.model_validate(result_dto)
