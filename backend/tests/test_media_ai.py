"""Unit and integration tests for Media AI, Physical Artifacts, 2-Videos/Day, .ICS, Attribution & Niches."""

from collections.abc import AsyncGenerator
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import StaticPool

from app.core.database import (
    SQLITE_SCHEMA_TRANSLATE_MAP,
    get_db_session,
    reset_session_factory,
    set_session_factory,
)
from app.core.event_bus import event_bus
from app.main import app
from app.modules.commerce.infrastructure.models import CommerceBase
from app.modules.identity.infrastructure.models import IdentityBase
from app.modules.media_ai.application.handlers import register_media_ai_event_handlers
from app.modules.media_ai.domain.entities import JobStatus, JobType, MediaJob
from app.modules.media_ai.domain.exceptions import (
    InvalidJobStateTransitionError,
    InvalidMediaSourceError,
)
from app.modules.media_ai.infrastructure.models import (
    MediaAiBase,
    MediaJobModel,
    ScheduledPostModel,
)
from app.modules.wallet.application.handlers import register_wallet_event_handlers
from app.modules.wallet.infrastructure.models import WalletBase


@pytest.fixture
async def sqlite_engine() -> AsyncGenerator[AsyncEngine, None]:
    """Creates a shared in-memory SQLite engine for all 4 bounded-context schemas."""
    base_engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        execution_options={"schema_translate_map": SQLITE_SCHEMA_TRANSLATE_MAP},
    )
    async with base_engine.begin() as conn:
        await conn.run_sync(IdentityBase.metadata.create_all)
        await conn.run_sync(WalletBase.metadata.create_all)
        await conn.run_sync(CommerceBase.metadata.create_all)
        await conn.run_sync(MediaAiBase.metadata.create_all)
    yield base_engine
    await base_engine.dispose()


@pytest.fixture
async def async_client(sqlite_engine: AsyncEngine) -> AsyncGenerator[AsyncClient, None]:
    """Configures test session factory, registers EventBus handlers, and yields client."""
    session_factory = async_sessionmaker(
        bind=sqlite_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )
    set_session_factory(session_factory)

    async def _override_get_db() -> AsyncGenerator[AsyncSession, None]:
        async with session_factory() as session:
            yield session

    app.dependency_overrides[get_db_session] = _override_get_db
    event_bus.clear()
    register_wallet_event_handlers(event_bus)
    register_media_ai_event_handlers(event_bus)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        yield client

    app.dependency_overrides.clear()
    event_bus.clear()
    reset_session_factory()


def test_media_job_domain_invariants_and_schema_isolation() -> None:
    """Verifies MediaJob & ScheduledPost state transitions and Law 2 isolation in media_ai_schema."""
    assert MediaJobModel.__table__.schema == "media_ai_schema"
    assert ScheduledPostModel.__table__.schema == "media_ai_schema"
    assert len(MediaJobModel.__table__.foreign_keys) == 0
    assert len(ScheduledPostModel.__table__.foreign_keys) == 0

    job = MediaJob(
        creator_id=uuid4(),
        job_type=JobType.VIRAL_SHORT_CLIP,
        source_url_or_prompt="  https://storage.superapp.io/raw/stream.mp4  ",
    )
    assert job.status == JobStatus.QUEUED
    assert job.progress_percent == 0
    assert job.source_url_or_prompt == "https://storage.superapp.io/raw/stream.mp4"

    processing = job.mark_processing(progress=45)
    assert processing.status == JobStatus.PROCESSING
    assert processing.progress_percent == 45

    completed = processing.mark_completed(
        {"output_video_url": "https://cdn.superapp.io/clips/123.mp4"}
    )
    assert completed.status == JobStatus.COMPLETED
    assert completed.progress_percent == 100

    # Completed job cannot transition to FAILED or PROCESSING
    with pytest.raises(InvalidJobStateTransitionError):
        completed.mark_failed("Should not be allowed")

    with pytest.raises(InvalidMediaSourceError):
        MediaJob(
            creator_id=uuid4(),
            job_type=JobType.AUTO_CAPTIONS_WHISPER,
            source_url_or_prompt="   ",
        )


async def test_enqueue_process_and_download_srt_with_linked_product(
    async_client: AsyncClient,
) -> None:
    """Verifies 202 Accepted enqueueing, multi-niche script generation, and .srt + .md downloads."""
    await async_client.post(
        "/api/v1/identity/register",
        json={
            "email": "creator_studio@superapp.io",
            "password": "StudioPassword123!",
            "full_name": "Marques Creator",
            "roles": ["USER", "CREATOR", "MERCHANT"],
        },
    )
    login_res = await async_client.post(
        "/api/v1/identity/login",
        json={
            "email": "creator_studio@superapp.io",
            "password": "StudioPassword123!",
        },
    )
    headers = {"Authorization": f"Bearer {login_res.json()['access_token']}"}

    # 1. Create a product in Commerce to link in the video showcase
    prod_res = await async_client.post(
        "/api/v1/commerce/products",
        json={
            "sku": "STUDIO-MIC-PRO",
            "title": "Micrófono Dinámico USB/XLR",
            "description": "Audio de estudio para creadores",
            "price_cents": 45_000_000,
            "stock_quantity": 25,
        },
        headers=headers,
    )
    assert prod_res.status_code == 201
    product_id = prod_res.json()["id"]

    # 2. Enqueue a VIRAL_SHORT_CLIP with RAP_CULTURE_VIRAL niche linked to product_id -> 202 Accepted
    enqueue_res = await async_client.post(
        "/api/v1/media-ai/jobs",
        json={
            "job_type": "VIRAL_SHORT_CLIP",
            "content_niche": "RAP_CULTURE_VIRAL",
            "source_url_or_prompt": "Análisis de barras y cultura hip-hop en vivo",
            "linked_product_id": product_id,
        },
        headers=headers,
    )
    assert enqueue_res.status_code == 202
    queued_job = enqueue_res.json()
    job_id = queued_job["id"]
    assert queued_job["status"] == "QUEUED"
    assert queued_job["content_niche"] == "RAP_CULTURE_VIRAL"
    assert queued_job["linked_product_id"] == product_id

    # 3. Trigger worker completion and verify COMPLETED state + CapCut cuts + SRT & MD downloads
    proc_res = await async_client.post(
        f"/api/v1/media-ai/jobs/{job_id}/process-sync",
        headers=headers,
    )
    assert proc_res.status_code == 200
    completed_job = proc_res.json()
    payload = completed_job["result_payload"]
    assert completed_job["status"] == "COMPLETED"
    assert completed_job["progress_percent"] == 100
    assert payload["content_niche"] == "RAP_CULTURE_VIRAL"
    assert "capcut_camera_cuts" in payload
    assert "Beat Drop 0-3s" in payload["ugc_hook_0_3s"]
    assert Path(payload["srt_file_path"]).is_file()
    assert Path(payload["script_markdown_path"]).is_file()

    # 4. Download .srt and .md production pack
    srt_res = await async_client.get(
        f"/api/v1/media-ai/jobs/{job_id}/download-srt",
        headers=headers,
    )
    assert srt_res.status_code == 200
    assert "00:00:00,000 --> 00:00:03,000" in srt_res.text

    pack_res = await async_client.get(
        f"/api/v1/media-ai/jobs/{job_id}/download-pack",
        headers=headers,
    )
    assert pack_res.status_code == 200
    assert "RAP_CULTURE_VIRAL" in pack_res.text
    assert "Mapa de Cortes CapCut" in pack_res.text


async def test_daily_two_videos_schedule_ics_and_sales_attribution(
    async_client: AsyncClient,
) -> None:
    """Verifies 2-videos/day slot scheduling, 409 slot conflict, .ics download, and reactive sales attribution."""
    pub_email = f"publisher_{uuid4().hex[:8]}@superapp.io"
    await async_client.post(
        "/api/v1/identity/register",
        json={
            "email": pub_email,
            "password": "PublisherPassword123!",
            "full_name": "Creator Publisher",
            "roles": ["USER", "CREATOR", "MERCHANT"],
        },
    )
    login_res = await async_client.post(
        "/api/v1/identity/login",
        json={
            "email": pub_email,
            "password": "PublisherPassword123!",
        },
    )
    headers = {"Authorization": f"Bearer {login_res.json()['access_token']}"}

    # Create a catalog product ($95,000 COP -> 9_500_000 cents)
    prod_res = await async_client.post(
        "/api/v1/commerce/products",
        json={
            "sku": f"COMBO-ERGO-{uuid4().hex[:8]}",
            "title": "Combo Setup Ergonómico: Lámpara Monitor + Soporte Laptop",
            "description": "Combo viral de productividad",
            "price_cents": 9_500_000,
            "stock_quantity": 20,
        },
        headers=headers,
    )
    product_id = prod_res.json()["id"]

    # Create 3 video jobs
    job1 = (
        await async_client.post(
            "/api/v1/media-ai/jobs",
            json={
                "job_type": "PRODUCT_SHOWCASE_VIDEO",
                "source_url_or_prompt": "https://storage.superapp.io/raw/video1.mp4",
                "linked_product_id": product_id,
            },
            headers=headers,
        )
    ).json()
    job2 = (
        await async_client.post(
            "/api/v1/media-ai/jobs",
            json={
                "job_type": "VIRAL_SHORT_CLIP",
                "source_url_or_prompt": "https://storage.superapp.io/raw/video2.mp4",
                "linked_product_id": product_id,
            },
            headers=headers,
        )
    ).json()
    job3 = (
        await async_client.post(
            "/api/v1/media-ai/jobs",
            json={
                "job_type": "AI_OUTFIT_RECOMMENDATION",
                "source_url_or_prompt": "Outfit urbano con Chaqueta RBR",
            },
            headers=headers,
        )
    ).json()

    # 1. Schedule Job 1 in SLOT_1_MIDDAY on 2026-11-18 -> 1/2
    sched1_res = await async_client.post(
        f"/api/v1/media-ai/jobs/{job1['id']}/schedule",
        json={
            "platform": "TIKTOK",
            "scheduled_date": "2026-11-18",
            "slot": "SLOT_1_MIDDAY",
        },
        headers=headers,
    )
    assert sched1_res.status_code == 201
    assert sched1_res.json()["slot"] == "SLOT_1_MIDDAY"

    # Attempting to book Job 3 into the exact same date & SLOT_1_MIDDAY must fail with 409 Conflict
    conflict_res = await async_client.post(
        f"/api/v1/media-ai/jobs/{job3['id']}/schedule",
        json={
            "platform": "INSTAGRAM_REELS",
            "scheduled_date": "2026-11-18",
            "slot": "SLOT_1_MIDDAY",
        },
        headers=headers,
    )
    assert conflict_res.status_code == 409

    # Schedule Job 2 in SLOT_2_EVENING on 2026-11-18 -> reaches 2/2 daily goal!
    sched2_res = await async_client.post(
        f"/api/v1/media-ai/jobs/{job2['id']}/schedule",
        json={
            "platform": "YOUTUBE_SHORTS",
            "scheduled_date": "2026-11-18",
            "slot": "SLOT_2_EVENING",
        },
        headers=headers,
    )
    assert sched2_res.status_code == 201

    streak_res = await async_client.get(
        "/api/v1/media-ai/schedule?target_date=2026-11-18",
        headers=headers,
    )
    assert streak_res.status_code == 200
    streak = streak_res.json()
    assert streak["scheduled_today_count"] == 2
    assert streak["daily_goal"] == 2
    assert streak["goal_completed"] is True

    # Verify Google Calendar .ics download with 15-minute VALARM
    ics_res = await async_client.get(
        f"/api/v1/media-ai/jobs/{job1['id']}/download-ics",
        headers=headers,
    )
    assert ics_res.status_code == 200
    assert "BEGIN:VCALENDAR" in ics_res.text
    assert "BEGIN:VEVENT" in ics_res.text
    assert "TRIGGER:-PT15M" in ics_res.text

    # 2. Place an order in Commerce attributed to job1['id'] -> reactive EventBus updates conversions!
    order_res = await async_client.post(
        "/api/v1/commerce/orders",
        json={
            "items": [{"product_id": product_id, "quantity": 2}],
            "payment_method": "CASH_ON_DELIVERY",
            "shipping_address": "Calle 93 #11-27, Bogotá",
            "idempotency_key": "order-attributed-to-video-001",
            "source_job_id": job1["id"],
        },
        headers=headers,
    )
    assert order_res.status_code == 201
    assert order_res.json()["source_job_id"] == job1["id"]

    # Check that conversions_count == 1 and revenue_attributed_cents == 19_000_000 ($190,000 COP)
    updated_schedule = (
        await async_client.get(
            "/api/v1/media-ai/schedule?target_date=2026-11-18",
            headers=headers,
        )
    ).json()
    assert updated_schedule["total_conversions"] == 1
    assert updated_schedule["total_revenue_attributed_cents"] == 19_000_000

    job1_post = next(
        p for p in updated_schedule["scheduled_posts"] if p["job_id"] == job1["id"]
    )
    assert job1_post["conversions_count"] == 1
    assert job1_post["revenue_attributed_cents"] == 19_000_000


async def test_enqueue_media_job_rejects_nonexistent_linked_product(
    async_client: AsyncClient,
) -> None:
    """Verifies 404 Not Found when linking a non-existent product_id."""
    await async_client.post(
        "/api/v1/identity/register",
        json={
            "email": "editor@superapp.io",
            "password": "EditorPassword123!",
            "full_name": "Video Editor",
            "roles": ["CREATOR"],
        },
    )
    login_res = await async_client.post(
        "/api/v1/identity/login",
        json={
            "email": "editor@superapp.io",
            "password": "EditorPassword123!",
        },
    )
    headers = {"Authorization": f"Bearer {login_res.json()['access_token']}"}

    fake_product_id = str(uuid4())
    bad_res = await async_client.post(
        "/api/v1/media-ai/jobs",
        json={
            "job_type": "VIRAL_SHORT_CLIP",
            "source_url_or_prompt": "https://storage.superapp.io/raw/clip.mp4",
            "linked_product_id": fake_product_id,
        },
        headers=headers,
    )
    assert bad_res.status_code == 404
    assert fake_product_id in bad_res.json()["detail"]


async def test_control_center_dashboard_returns_200_ok(
    async_client: AsyncClient,
) -> None:
    """Verifies GET /dashboard serves the interactive Super App Control Center HTML."""
    res = await async_client.get("/dashboard")
    assert res.status_code == 200
    assert "text/html" in res.headers.get("content-type", "")
    assert "Super App Ecosystem — Live Control Center" in res.text
    assert "Ajuste Dinámico de Precio (IA)" in res.text
    assert "Quemar Subtítulos Estilo TikTok en el MP4" in res.text
    assert "Descargar Short Listo para TikTok (.MP4)" in res.text


async def test_real_video_pipeline_graceful_fallback_and_mp4_endpoint(
    async_client: AsyncClient,
) -> None:
    """Verifies RealVideoClipperPipeline binary auto-detection, offline fallback, and /download-mp4."""
    from app.modules.media_ai.infrastructure.binary_locator import (
        get_media_binaries_status,
    )

    binaries = get_media_binaries_status(auto_install_ffmpeg=False)
    assert hasattr(binaries, "ffmpeg_path")
    assert hasattr(binaries, "deno_path")

    await async_client.post(
        "/api/v1/identity/register",
        json={
            "email": "clipper@superapp.io",
            "password": "ClipperPassword123!",
            "full_name": "Real Video Clipper",
            "roles": ["CREATOR"],
        },
    )
    login_res = await async_client.post(
        "/api/v1/identity/login",
        json={
            "email": "clipper@superapp.io",
            "password": "ClipperPassword123!",
        },
    )
    headers = {"Authorization": f"Bearer {login_res.json()['access_token']}"}

    enqueue_res = await async_client.post(
        "/api/v1/media-ai/jobs",
        json={
            "job_type": "VIRAL_SHORT_CLIP",
            "content_niche": "YOUTUBE_HIGHLIGHT_CLIP",
            "source_url_or_prompt": "https://storage.superapp.io/demo/highlight_stream.mp4",
            "use_real_pipeline": True,
        },
        headers=headers,
    )
    assert enqueue_res.status_code == 202
    job_data = enqueue_res.json()
    job_id = job_data["id"]
    assert job_data["use_real_pipeline"] is True

    proc_res = await async_client.post(
        f"/api/v1/media-ai/jobs/{job_id}/process-sync",
        headers=headers,
    )
    assert proc_res.status_code == 200
    payload = proc_res.json()["result_payload"]
    assert payload["pipeline_mode"] == "graceful_fallback"
    assert Path(payload["mp4_file_path"]).is_file()

    mp4_res = await async_client.get(
        f"/api/v1/media-ai/jobs/{job_id}/download-mp4",
        headers=headers,
    )
    assert mp4_res.status_code == 200
    assert "video/mp4" in mp4_res.headers.get("content-type", "")
    assert b"ftypmp42" in mp4_res.content


async def test_tiktok_subtitle_burn_and_peak_clip_offset(
    async_client: AsyncClient,
) -> None:
    """Verifies Audio Peak Finder window selection, SRT timestamp shifting, and burn_subtitles parameter."""
    from app.modules.media_ai.infrastructure.video_pipeline import (
        find_viral_audio_peak_start_sec,
        shift_and_clip_srt_to_window,
    )

    # 1. Verify Audio Peak Finder picks the 20s window with highest vocal word density (starting at 15.0s)
    segments = [
        (0.0, 4.0, "Intro suave"),
        (15.0, 22.0, "Aquí empieza el clímax viral con muchísima energía y ritmo rápido"),
        (22.0, 32.0, "Barras consecutivas sin pausa explicando el secreto principal del video"),
        (45.0, 50.0, "Outro final"),
    ]
    peak_start = find_viral_audio_peak_start_sec(segments, clip_duration_sec=20.0)
    assert peak_start == 15.0

    # 2. Verify SRT timestamp shifting aligns captions to clip_start_sec=15.0
    original_srt = (
        "1\n00:00:00,000 --> 00:00:04,000\nIntro suave\n\n"
        "2\n00:00:15,000 --> 00:00:22,000\nAquí empieza el clímax viral\n\n"
        "3\n00:00:22,000 --> 00:00:32,000\nBarras consecutivas sin pausa\n"
    )
    shifted_srt = shift_and_clip_srt_to_window(
        original_srt,
        clip_start_sec=15.0,
        clip_duration_sec=20.0,
    )
    assert "00:00:00,000 --> 00:00:07,000" in shifted_srt
    assert "00:00:07,000 --> 00:00:17,000" in shifted_srt
    assert "Intro suave" not in shifted_srt

    # 3. Verify API end-to-end with burn_subtitles=True
    await async_client.post(
        "/api/v1/identity/register",
        json={
            "email": "subburner@superapp.io",
            "password": "BurnerPassword123!",
            "full_name": "TikTok Subtitle Burner",
            "roles": ["CREATOR"],
        },
    )
    login_res = await async_client.post(
        "/api/v1/identity/login",
        json={
            "email": "subburner@superapp.io",
            "password": "BurnerPassword123!",
        },
    )
    headers = {"Authorization": f"Bearer {login_res.json()['access_token']}"}

    enqueue_res = await async_client.post(
        "/api/v1/media-ai/jobs",
        json={
            "job_type": "VIRAL_SHORT_CLIP",
            "content_niche": "RAP_CULTURE_VIRAL",
            "source_url_or_prompt": "https://storage.superapp.io/demo/rap_session.mp4",
            "use_real_pipeline": True,
            "burn_subtitles": True,
        },
        headers=headers,
    )
    assert enqueue_res.status_code == 202
    job_data = enqueue_res.json()
    assert job_data["burn_subtitles"] is True

    proc_res = await async_client.post(
        f"/api/v1/media-ai/jobs/{job_data['id']}/process-sync",
        headers=headers,
    )
    assert proc_res.status_code == 200
    payload = proc_res.json()["result_payload"]
    assert payload["subtitle_style"] == "tiktok_bold_outline"
    assert payload["clip_start_offset_sec"] == "0.0"


async def test_niche_performance_analytics_aggregation(
    async_client: AsyncClient,
) -> None:
    """Verifies GET /api/v1/media-ai/analytics/by-niche groups jobs, scheduled posts, conversions, and COP revenue."""
    niche_email = f"niche_roi_{uuid4().hex[:8]}@superapp.io"
    await async_client.post(
        "/api/v1/identity/register",
        json={
            "email": niche_email,
            "password": "NichePassword123!",
            "full_name": "Niche ROI Creator",
            "roles": ["USER", "CREATOR", "MERCHANT"],
        },
    )
    login_res = await async_client.post(
        "/api/v1/identity/login",
        json={
            "email": niche_email,
            "password": "NichePassword123!",
        },
    )
    headers = {"Authorization": f"Bearer {login_res.json()['access_token']}"}

    # Create a catalog product to sell via attributed video orders
    prod_res = await async_client.post(
        "/api/v1/commerce/products",
        json={
            "sku": f"NICHE-CAP-{uuid4().hex[:8]}",
            "title": "Gorra Estructurada RBR Streetwear",
            "description": "Edición bordada 3D",
            "price_cents": 8_500_000,  # $85,000 COP
            "unit_cost_cents": 3_000_000,
            "stock_quantity": 20,
        },
        headers=headers,
    )
    assert prod_res.status_code == 201
    product_id = prod_res.json()["id"]

    # Enqueue 2 jobs in RAP_CULTURE_VIRAL and 1 job in DESK_SETUP_UGC
    rap_job_1 = (
        await async_client.post(
            "/api/v1/media-ai/jobs",
            json={
                "job_type": "VIRAL_SHORT_CLIP",
                "content_niche": "RAP_CULTURE_VIRAL",
                "source_url_or_prompt": "https://storage.superapp.io/raw/rap_bar_1.mp4",
                "linked_product_id": product_id,
            },
            headers=headers,
        )
    ).json()

    rap_job_2 = (
        await async_client.post(
            "/api/v1/media-ai/jobs",
            json={
                "job_type": "VIRAL_SHORT_CLIP",
                "content_niche": "RAP_CULTURE_VIRAL",
                "source_url_or_prompt": "https://storage.superapp.io/raw/rap_bar_2.mp4",
                "linked_product_id": product_id,
            },
            headers=headers,
        )
    ).json()

    desk_job = (
        await async_client.post(
            "/api/v1/media-ai/jobs",
            json={
                "job_type": "PRODUCT_SHOWCASE_VIDEO",
                "content_niche": "DESK_SETUP_UGC",
                "source_url_or_prompt": "https://storage.superapp.io/raw/desk_1.mp4",
                "linked_product_id": product_id,
            },
            headers=headers,
        )
    ).json()

    # Schedule rap_job_1 and desk_job
    await async_client.post(
        f"/api/v1/media-ai/jobs/{rap_job_1['id']}/schedule",
        json={
            "platform": "TIKTOK",
            "scheduled_date": "2026-11-19",
            "slot": "SLOT_1_MIDDAY",
        },
        headers=headers,
    )
    await async_client.post(
        f"/api/v1/media-ai/jobs/{desk_job['id']}/schedule",
        json={
            "platform": "TIKTOK",
            "scheduled_date": "2026-11-19",
            "slot": "SLOT_2_EVENING",
        },
        headers=headers,
    )

    # Attribute 2 orders to rap_job_1 ($85,000 + $170,000 = $255,000 COP) and 1 order to desk_job ($85,000 COP)
    await async_client.post(
        "/api/v1/commerce/orders",
        json={
            "items": [{"product_id": product_id, "quantity": 1}],
            "payment_method": "CASH_ON_DELIVERY",
            "shipping_address": "Calle 80 #12-10, Bogotá",
            "idempotency_key": "niche-roi-order-1",
            "source_job_id": rap_job_1["id"],
        },
        headers=headers,
    )
    await async_client.post(
        "/api/v1/commerce/orders",
        json={
            "items": [{"product_id": product_id, "quantity": 2}],
            "payment_method": "CASH_ON_DELIVERY",
            "shipping_address": "Calle 80 #12-10, Bogotá",
            "idempotency_key": "niche-roi-order-2",
            "source_job_id": rap_job_1["id"],
        },
        headers=headers,
    )
    await async_client.post(
        "/api/v1/commerce/orders",
        json={
            "items": [{"product_id": product_id, "quantity": 1}],
            "payment_method": "CASH_ON_DELIVERY",
            "shipping_address": "Calle 80 #12-10, Bogotá",
            "idempotency_key": "niche-roi-order-3",
            "source_job_id": desk_job["id"],
        },
        headers=headers,
    )

    # Query GET /api/v1/media-ai/analytics/by-niche
    analytics_res = await async_client.get(
        "/api/v1/media-ai/analytics/by-niche",
        headers=headers,
    )
    assert analytics_res.status_code == 200
    analytics = analytics_res.json()
    assert analytics["top_performing_niche"] == "RAP_CULTURE_VIRAL"
    assert analytics["total_videos_created"] == 3
    assert analytics["total_videos_scheduled"] == 2
    assert analytics["total_conversions"] == 3
    assert analytics["total_revenue_attributed_cents"] == 34_000_000
    assert len(analytics["niches"]) == 4

    by_niche = {n["content_niche"]: n for n in analytics["niches"]}
    rap_metrics = by_niche["RAP_CULTURE_VIRAL"]
    assert rap_metrics["total_videos_created"] == 2
    assert rap_metrics["total_videos_scheduled"] == 1
    assert rap_metrics["conversions_count"] == 2
    assert rap_metrics["revenue_attributed_cents"] == 25_500_000
    assert rap_metrics["conversions_per_video"] == 1.0

    desk_metrics = by_niche["DESK_SETUP_UGC"]
    assert desk_metrics["total_videos_created"] == 1
    assert desk_metrics["total_videos_scheduled"] == 1
    assert desk_metrics["conversions_count"] == 1
    assert desk_metrics["revenue_attributed_cents"] == 8_500_000
    assert desk_metrics["conversions_per_video"] == 1.0
    assert rap_job_2["id"] != rap_job_1["id"]


async def test_media_job_enriches_cross_sell_bundle(
    async_client: AsyncClient,
) -> None:
    """Verifies that Media AI video pipeline enriches result_payload and script_tiktok.md with cross-sell bundle."""
    creator_email = f"creator_cross_{uuid4().hex[:8]}@superapp.io"
    await async_client.post(
        "/api/v1/identity/register",
        json={
            "email": creator_email,
            "password": "CreatorPassword123!",
            "full_name": "Outfit Video Creator",
            "roles": ["USER", "CREATOR", "MERCHANT"],
        },
    )
    login_res = await async_client.post(
        "/api/v1/identity/login",
        json={
            "email": creator_email,
            "password": "CreatorPassword123!",
        },
    )
    headers = {"Authorization": f"Bearer {login_res.json()['access_token']}"}

    # 1. Create 2 products in menswear category
    jacket_res = await async_client.post(
        "/api/v1/commerce/products",
        json={
            "sku": f"OUTFIT-JKT-{uuid4().hex[:6].upper()}",
            "title": "Chaqueta Cortavientos Urban",
            "description": "Cortavientos",
            "price_cents": 180_000_00,
            "unit_cost_cents": 75_000_00,
            "stock_quantity": 5,
            "category_tag": "MENSWEAR",
            "complement_tags": ["MENSWEAR"],
        },
        headers=headers,
    )
    assert jacket_res.status_code == 201
    jacket_id = jacket_res.json()["id"]

    pants_res = await async_client.post(
        "/api/v1/commerce/products",
        json={
            "sku": f"OUTFIT-PNT-{uuid4().hex[:6].upper()}",
            "title": "Jogger Cargo Táctico",
            "description": "Jogger",
            "price_cents": 130_000_00,
            "unit_cost_cents": 55_000_00,
            "stock_quantity": 5,
            "category_tag": "MENSWEAR",
            "complement_tags": ["MENSWEAR"],
        },
        headers=headers,
    )
    assert pants_res.status_code == 201
    pants_id = pants_res.json()["id"]

    # 2. Enqueue Media Job linking to the jacket
    enqueue_res = await async_client.post(
        "/api/v1/media-ai/jobs",
        json={
            "job_type": "VIRAL_SHORT_CLIP",
            "content_niche": "MENSWEAR_LOOKBOOK",
            "source_url_or_prompt": "3 outfits urbanos con chaqueta cortavientos",
            "linked_product_id": jacket_id,
        },
        headers=headers,
    )
    assert enqueue_res.status_code == 202
    job_id = enqueue_res.json()["id"]

    # 3. Process the job synchronously
    proc_res = await async_client.post(
        f"/api/v1/media-ai/jobs/{job_id}/process-sync",
        headers=headers,
    )
    assert proc_res.status_code == 200
    job_data = proc_res.json()
    assert job_data["status"] == "COMPLETED"
    payload = job_data["result_payload"]

    assert "cross_sell_bundle_name" in payload
    assert "Combo Outfit IA" in payload["cross_sell_bundle_name"]
    assert payload["cross_sell_complement_id"] == pants_id
    assert "cross_sell_bundle_price" in payload
    assert "cross_sell_bundle_savings" in payload

    # 4. Check Markdown production guide has cross-sell section
    from app.modules.media_ai.infrastructure.repositories import artifact_generator
    md_content = artifact_generator.read_script_markdown(UUID(job_id))
    assert md_content is not None
    assert "## 🛍️ Oferta de Venta Cruzada / Outfit Completo" in md_content
    assert payload["cross_sell_bundle_name"] in md_content


async def test_media_artifact_retention_cleanup_preserves_roi_metrics(
    async_client: AsyncClient,
) -> None:
    """Verifies POST /api/v1/media-ai/maintenance/cleanup purges old disk artifacts while preserving ROI metrics."""
    from datetime import UTC, datetime, timedelta
    from sqlalchemy import update

    from app.core.database import get_session_factory
    from app.modules.media_ai.infrastructure.models import MediaJobModel
    from app.modules.media_ai.infrastructure.repositories import MEDIA_OUTPUTS_DIR

    email = f"cleanup_creator_{uuid4().hex[:8]}@superapp.io"
    await async_client.post(
        "/api/v1/identity/register",
        json={
            "email": email,
            "password": "CleanupPassword123!",
            "full_name": "Retention Creator",
            "roles": ["USER", "CREATOR", "MERCHANT"],
        },
    )
    login_res = await async_client.post(
        "/api/v1/identity/login",
        json={"email": email, "password": "CleanupPassword123!"},
    )
    headers = {"Authorization": f"Bearer {login_res.json()['access_token']}"}

    # 1. Create a Commerce product for attributed sales
    prod_res = await async_client.post(
        "/api/v1/commerce/products",
        json={
            "sku": f"CLEANUP-JKT-{uuid4().hex[:6].upper()}",
            "title": "Chaqueta Bomber Retention Pro",
            "description": "Producto para validar retención ROI",
            "price_cents": 12_000_000,
            "unit_cost_cents": 4_500_000,
            "stock_quantity": 10,
            "category_tag": "MENSWEAR",
        },
        headers=headers,
    )
    assert prod_res.status_code == 201
    product_id = prod_res.json()["id"]

    # 2. Enqueue & process an expired job and a fresh job
    old_enqueue = await async_client.post(
        "/api/v1/media-ai/jobs",
        json={
            "job_type": "VIRAL_SHORT_CLIP",
            "content_niche": "MENSWEAR_LOOKBOOK",
            "source_url_or_prompt": "https://storage.superapp.io/demo/old_lookbook.mp4",
            "linked_product_id": product_id,
        },
        headers=headers,
    )
    assert old_enqueue.status_code == 202
    old_job_id = old_enqueue.json()["id"]

    old_proc = await async_client.post(
        f"/api/v1/media-ai/jobs/{old_job_id}/process-sync",
        headers=headers,
    )
    assert old_proc.status_code == 200

    # Ensure all 4 heavy/temporary artifact files exist on disk for the old job
    old_job_dir = MEDIA_OUTPUTS_DIR / old_job_id
    source_mp4 = old_job_dir / "source_720p.mp4"
    source_mp4.write_bytes(b"\x00\x00\x00\x18ftypmp42" + b"X" * 2048)
    short_mp4 = old_job_dir / "short_9x16.mp4"
    captions_srt = old_job_dir / "captions.srt"
    pack_json = old_job_dir / "production_pack.json"
    assert source_mp4.is_file()
    assert short_mp4.is_file()
    assert captions_srt.is_file()
    assert pack_json.is_file()

    # Schedule the old job and attribute a real order ($240,000 COP = 24_000_000 cents)
    sched_res = await async_client.post(
        f"/api/v1/media-ai/jobs/{old_job_id}/schedule",
        json={
            "platform": "TIKTOK",
            "scheduled_date": "2026-10-01",
            "slot": "SLOT_1_MIDDAY",
        },
        headers=headers,
    )
    assert sched_res.status_code == 201

    order_res = await async_client.post(
        "/api/v1/commerce/orders",
        json={
            "items": [{"product_id": product_id, "quantity": 2}],
            "payment_method": "CASH_ON_DELIVERY",
            "shipping_address": "Calle 93 #11-27, Bogotá",
            "idempotency_key": f"cleanup-roi-order-{uuid4().hex[:6]}",
            "source_job_id": old_job_id,
        },
        headers=headers,
    )
    assert order_res.status_code == 201

    # Also create a fresh job (< 30 days) whose artifacts must NOT be purged
    fresh_enqueue = await async_client.post(
        "/api/v1/media-ai/jobs",
        json={
            "job_type": "PRODUCT_SHOWCASE_VIDEO",
            "content_niche": "DESK_SETUP_UGC",
            "source_url_or_prompt": "https://storage.superapp.io/demo/fresh_clip.mp4",
            "linked_product_id": product_id,
        },
        headers=headers,
    )
    assert fresh_enqueue.status_code == 202
    fresh_job_id = fresh_enqueue.json()["id"]
    fresh_proc = await async_client.post(
        f"/api/v1/media-ai/jobs/{fresh_job_id}/process-sync",
        headers=headers,
    )
    assert fresh_proc.status_code == 200
    fresh_pack_json = MEDIA_OUTPUTS_DIR / fresh_job_id / "production_pack.json"
    assert fresh_pack_json.is_file()

    # 3. Backdate old_job to 45 days ago in media_ai_schema
    expired_ts = datetime.now(UTC) - timedelta(days=45)
    session_factory = get_session_factory()
    async with session_factory() as session:
        await session.execute(
            update(MediaJobModel)
            .where(MediaJobModel.id == UUID(old_job_id))
            .values(created_at=expired_ts)
        )
        await session.commit()

    # 4. Trigger maintenance cleanup endpoint (retention_days=30)
    cleanup_res = await async_client.post(
        "/api/v1/media-ai/maintenance/cleanup",
        params={"retention_days": 30},
        headers=headers,
    )
    assert cleanup_res.status_code == 200
    summary = cleanup_res.json()
    assert summary["retention_days"] == 30
    assert summary["jobs_scanned"] == 1
    assert summary["files_deleted"] == 4
    assert summary["bytes_reclaimed"] > 2048
    assert summary["retained_metrics_count"] == 1

    # 5. Physical heavy artifacts for the old job must be gone, while fresh job files remain
    assert not source_mp4.exists()
    assert not short_mp4.exists()
    assert not captions_srt.exists()
    assert not pack_json.exists()
    assert fresh_pack_json.is_file()

    # 6. Verify old job record is retained with artifacts_purged=True and content_niche intact
    old_job_after = (
        await async_client.get(f"/api/v1/media-ai/jobs/{old_job_id}", headers=headers)
    ).json()
    assert old_job_after["artifacts_purged"] is True
    assert old_job_after["result_payload"]["artifacts_purged"] == "true"
    assert old_job_after["content_niche"] == "MENSWEAR_LOOKBOOK"

    # 7. Verify ROI attribution metrics (conversions_count & revenue_attributed_cents) are 100% intact
    schedule_after = (
        await async_client.get("/api/v1/media-ai/schedule", headers=headers)
    ).json()
    assert schedule_after["total_conversions"] == 1
    assert schedule_after["total_revenue_attributed_cents"] == 24_000_000

    analytics_after = (
        await async_client.get("/api/v1/media-ai/analytics/by-niche", headers=headers)
    ).json()
    by_niche = {n["content_niche"]: n for n in analytics_after["niches"]}
    menswear_roi = by_niche["MENSWEAR_LOOKBOOK"]
    assert menswear_roi["conversions_count"] == 1
    assert menswear_roi["revenue_attributed_cents"] == 24_000_000

    # 8. Verify idempotency: running cleanup again deletes 0 files and preserves metrics
    second_cleanup = await async_client.post(
        "/api/v1/media-ai/maintenance/cleanup",
        json={"retention_days": 30},
        headers=headers,
    )
    assert second_cleanup.status_code == 200
    second_summary = second_cleanup.json()
    assert second_summary["jobs_scanned"] == 1
    assert second_summary["files_deleted"] == 0
    assert second_summary["bytes_reclaimed"] == 0
    assert second_summary["retained_metrics_count"] == 1
