"""Architectural Guard Tests (Laws 1, 3 & 4 of ARCHITECTURE.md + OpenAPI & Android Readiness)."""

import ast
import json
from pathlib import Path
import re
import pytest

# Resolve paths relative to this test file so pytest works from root or backend/
BACKEND_DIR = Path(__file__).resolve().parent.parent
MONOREPO_ROOT = BACKEND_DIR.parent
MODULES_DIR = BACKEND_DIR / "app" / "modules"
MOBILE_DIR = MONOREPO_ROOT / "client-mobile"
MOBILE_FEATURES_DIR = MOBILE_DIR / "features"
OPENAPI_CONTRACT_PATH = MONOREPO_ROOT / "shared-contracts" / "openapi.json"

FORBIDDEN_DOMAIN_FRAMEWORKS = {"fastapi", "sqlalchemy"}
FORBIDDEN_KOTLIN_DOMAIN_IMPORTS = ("androidx.", "retrofit2.", "okhttp3.")


def get_module_names() -> list[str]:
    """Returns all bounded-context module names under backend/app/modules."""
    return [
        d.name
        for d in MODULES_DIR.iterdir()
        if d.is_dir() and not d.name.startswith("__")
    ]


def test_no_cross_module_internal_imports() -> None:
    """Law 1 (Backend): Guarantees no module imports internal layers of another module."""
    modules = get_module_names()
    assert set(modules) >= {"identity", "media_ai", "commerce", "wallet"}

    for module in modules:
        other_modules = [m for m in modules if m != module]
        module_path = MODULES_DIR / module

        for py_file in module_path.rglob("*.py"):
            tree = ast.parse(py_file.read_text(encoding="utf-8-sig"))
            for node in ast.walk(tree):
                if isinstance(node, ast.ImportFrom) and node.module:
                    for other in other_modules:
                        forbidden_prefix = f"app.modules.{other}."
                        allowed_api = f"app.modules.{other}.public_api"
                        if (
                            node.module.startswith(forbidden_prefix)
                            and node.module != allowed_api
                        ):
                            pytest.fail(
                                f"Violación Arquitectónica (Ley 1) en {py_file}: "
                                f"Importación ilegal '{node.module}'. "
                                f"Solo se permite importar desde '{allowed_api}' o usar Event Bus."
                            )
                elif isinstance(node, ast.Import):
                    for alias in node.names:
                        for other in other_modules:
                            forbidden_prefix = f"app.modules.{other}."
                            allowed_api = f"app.modules.{other}.public_api"
                            if (
                                alias.name.startswith(forbidden_prefix)
                                and alias.name != allowed_api
                            ):
                                pytest.fail(
                                    f"Violación Arquitectónica (Ley 1) en {py_file}: "
                                    f"Importación ilegal '{alias.name}'. "
                                    f"Solo se permite importar desde '{allowed_api}' o usar Event Bus."
                                )


def test_domain_purity_no_framework_imports() -> None:
    """Law 3 (Backend): Guarantees no domain/ folder imports fastapi or sqlalchemy."""
    modules = get_module_names()

    for module in modules:
        domain_path = MODULES_DIR / module / "domain"
        assert domain_path.is_dir(), f"Falta la capa obligatoria domain/ en {module}"

        for py_file in domain_path.rglob("*.py"):
            tree = ast.parse(py_file.read_text(encoding="utf-8-sig"))
            for node in ast.walk(tree):
                if isinstance(node, ast.ImportFrom) and node.module:
                    root_pkg = node.module.split(".")[0]
                    if root_pkg in FORBIDDEN_DOMAIN_FRAMEWORKS:
                        pytest.fail(
                            f"Violación de Pureza de Dominio (Ley 3) en {py_file}: "
                            f"Prohibido importar '{node.module}' dentro de domain/."
                        )
                elif isinstance(node, ast.Import):
                    for alias in node.names:
                        root_pkg = alias.name.split(".")[0]
                        if root_pkg in FORBIDDEN_DOMAIN_FRAMEWORKS:
                            pytest.fail(
                                f"Violación de Pureza de Dominio (Ley 3) en {py_file}: "
                                f"Prohibido importar '{alias.name}' dentro de domain/."
                            )


def test_openapi_contract_is_up_to_date() -> None:
    """Verifies shared-contracts/openapi.json, docker-compose.yml, Dockerfile, and init-schemas.sql."""
    assert OPENAPI_CONTRACT_PATH.is_file(), (
        f"Falta el contrato OpenAPI en {OPENAPI_CONTRACT_PATH}. "
        "Ejecuta backend/scripts/export_openapi.py."
    )
    contract = json.loads(OPENAPI_CONTRACT_PATH.read_text(encoding="utf-8"))
    paths: dict[str, object] = contract.get("paths", {})

    required_prefixes = (
        "/api/v1/identity/",
        "/api/v1/wallet/",
        "/api/v1/commerce/",
        "/api/v1/media-ai/",
    )
    for prefix in required_prefixes:
        assert any(route.startswith(prefix) for route in paths), (
            f"shared-contracts/openapi.json no contiene rutas para '{prefix}'."
        )

    # Production Infrastructure & Multi-Schema Isolation validation (Law 2 & Scalability)
    docker_compose_path = MONOREPO_ROOT / "docker-compose.yml"
    assert docker_compose_path.is_file(), f"Falta docker-compose.yml en {docker_compose_path}"
    compose_content = docker_compose_path.read_text(encoding="utf-8")
    assert "postgres:" in compose_content
    assert "redis:" in compose_content
    assert "backend:" in compose_content
    assert "init-schemas.sql" in compose_content
    assert "healthz" in compose_content
    assert "OUTBOX_RETRY_WORKER_ENABLED" in compose_content

    dockerfile_path = BACKEND_DIR / "Dockerfile"
    assert dockerfile_path.is_file(), f"Falta backend/Dockerfile en {dockerfile_path}"
    dockerfile_content = dockerfile_path.read_text(encoding="utf-8")
    assert "python:3.12-slim" in dockerfile_content
    assert "ffmpeg" in dockerfile_content
    assert "requirements.txt" in dockerfile_content
    assert "--proxy-headers" in dockerfile_content


    init_schemas_path = MONOREPO_ROOT / "infra" / "postgres" / "init-schemas.sql"
    assert init_schemas_path.is_file(), f"Falta init-schemas.sql en {init_schemas_path}"
    schemas_sql = init_schemas_path.read_text(encoding="utf-8")
    for schema_name in (
        "identity_schema",
        "wallet_schema",
        "commerce_schema",
        "media_ai_schema",
    ):
        assert schema_name in schemas_sql, (
            f"init-schemas.sql no declara el esquema obligatorio '{schema_name}' (Ley 2)."
        )


def test_mobile_udf_and_feature_isolation() -> None:
    """Laws 1, 3 & 4 (Mobile) + Android Studio Readiness: Manifest, MainActivity, Lottie & UDF."""
    assert MOBILE_FEATURES_DIR.is_dir(), "Falta client-mobile/features/"

    # Verify Android Studio executable shell files exist and are valid
    manifest_path = MOBILE_DIR / "app" / "src" / "main" / "AndroidManifest.xml"
    main_activity_path = MOBILE_DIR / "app" / "MainActivity.kt"
    lottie_asset_path = MOBILE_DIR / "app" / "src" / "main" / "assets" / "pet_mascot.json"

    assert manifest_path.is_file(), f"Falta AndroidManifest.xml en {manifest_path}"
    manifest_text = manifest_path.read_text(encoding="utf-8-sig")
    assert "android.permission.INTERNET" in manifest_text
    assert 'android:usesCleartextTraffic="true"' in manifest_text

    assert main_activity_path.is_file(), f"Falta MainActivity.kt en {main_activity_path}"
    assert lottie_asset_path.is_file(), f"Falta el asset Lottie en {lottie_asset_path}"
    lottie_json = json.loads(lottie_asset_path.read_text(encoding="utf-8-sig"))
    assert "layers" in lottie_json and "v" in lottie_json

    api_service_path = MOBILE_DIR / "core" / "network" / "SuperAppApiService.kt"
    assert api_service_path.is_file(), f"Falta SuperAppApiService.kt en {api_service_path}"
    api_service_source = api_service_path.read_text(encoding="utf-8-sig")
    for required_endpoint in (
        "api/v1/commerce/orders/{orderId}/deliver",
        "api/v1/commerce/orders/{orderId}/ship",
        "api/v1/commerce/orders/{orderId}/messages",
        "api/v1/commerce/coupons",
        "api/v1/commerce/analytics/summary",
        "api/v1/commerce/products/{productId}/dynamic-price",
        "api/v1/media-ai/jobs/{jobId}/schedule",
        "api/v1/media-ai/schedule",
        "api/v1/media-ai/jobs/{jobId}/download-ics",
        "api/v1/media-ai/jobs/{jobId}/download-pack",
        "api/v1/media-ai/analytics/by-niche",
    ):
        assert required_endpoint in api_service_source, (
            f"Falta sincronizar el endpoint '{required_endpoint}' en SuperAppApiService.kt"
        )

    features = [
        d.name
        for d in MOBILE_FEATURES_DIR.iterdir()
        if d.is_dir() and d.name.startswith("feat_")
    ]
    assert set(features) >= {"feat_auth", "feat_wallet", "feat_shop", "feat_studio"}

    public_mutable_flow_pattern = re.compile(
        r"^\s*(?:public\s+)?(?:val|var)\s+\w+\s*(?::\s*MutableStateFlow|\s*=\s*MutableStateFlow)",
        re.MULTILINE,
    )

    for feat in features:
        other_features = [f for f in features if f != feat]
        feat_path = MOBILE_FEATURES_DIR / feat
        kt_files = [
            f for f in feat_path.rglob("*.kt") if not f.name.endswith(".gradle.kts")
        ]
        assert kt_files, f"El módulo móvil '{feat}' no contiene archivos Kotlin (.kt)."

        for kt_file in kt_files:
            source = kt_file.read_text(encoding="utf-8-sig")

            # 1. Law 1 (Mobile): No cross-feature internal imports
            for line in source.splitlines():
                stripped = line.strip()
                if stripped.startswith("import "):
                    imported_pkg = stripped.removeprefix("import ").strip()
                    for other in other_features:
                        forbidden_prefix = f"co.superapp.features.{other}."
                        if imported_pkg.startswith(forbidden_prefix):
                            pytest.fail(
                                f"Violación Arquitectónica Móvil (Ley 1) en {kt_file}: "
                                f"Importación cruzada ilegal '{imported_pkg}' desde '{feat}'."
                            )

                    # 2. Law 3 (Mobile Domain Purity): domain/ cannot import Android/Retrofit/Room
                    if "domain" in kt_file.parts:
                        if imported_pkg.startswith(FORBIDDEN_KOTLIN_DOMAIN_IMPORTS):
                            pytest.fail(
                                f"Violación de Pureza de Dominio Móvil (Ley 3) en {kt_file}: "
                                f"Prohibido importar '{imported_pkg}' en domain/."
                            )

            # 3. Law 4 (UDF): ViewModels must never expose public MutableStateFlow
            if "ViewModel" in source and public_mutable_flow_pattern.search(source):
                pytest.fail(
                    f"Violación UDF (Ley 4) en {kt_file}: "
                    "Un ViewModel expone MutableStateFlow público. "
                    "Usa 'private val _uiState = MutableStateFlow(...)' y expón 'StateFlow<UiState>'."
                )


@pytest.mark.asyncio
async def test_hybrid_event_bus_factory_and_redis_adapter() -> None:
    """Verifies hybrid EventBus factory and RedisStreamsEventBus XADD serialization contract."""
    from dataclasses import dataclass
    from unittest.mock import AsyncMock
    from app.core.event_bus import (
        DomainEvent,
        EventBus,
        InMemoryEventBus,
        RedisStreamsEventBus,
        create_event_bus,
    )

    # 1. Factory default fallback
    bus_default = create_event_bus()
    assert isinstance(bus_default, InMemoryEventBus)
    assert isinstance(bus_default, EventBus)

    # 2. Factory force Redis instance
    bus_redis = create_event_bus(force_redis=True)
    assert isinstance(bus_redis, RedisStreamsEventBus)
    assert isinstance(bus_redis, EventBus)

    # 3. Stream naming and serialization check
    @dataclass(frozen=True, kw_only=True)
    class DummyOrderEvent(DomainEvent):
        order_code: str
        amount_cop: int

    event = DummyOrderEvent(order_code="ORD-2026-X", amount_cop=9500000)
    stream_key = bus_redis.get_stream_key(type(event).__name__)
    assert stream_key == "superapp:events:DummyOrderEvent"

    # 4. Mock client to verify XADD interaction without live Redis server requirement
    mock_redis = AsyncMock()
    mock_redis.xadd = AsyncMock(return_value="1700000000000-0")
    bus_redis._client = mock_redis

    await bus_redis.publish(event)

    mock_redis.xadd.assert_awaited_once()
    args, kwargs = mock_redis.xadd.call_args
    assert args[0] == "superapp:events:DummyOrderEvent"
    assert args[1]["event_name"] == "DummyOrderEvent"
    assert "ORD-2026-X" in args[1]["payload"]
    assert "9500000" in args[1]["payload"]


def test_ci_workflow_and_mobile_variant_parity() -> None:
    """Verifies GitHub Actions CI pipeline and mobile Android variant parity without architectural violations."""
    # 1. CI Workflow Validation
    ci_workflow_path = MONOREPO_ROOT / ".github" / "workflows" / "ci.yml"
    assert ci_workflow_path.exists(), "El archivo de workflow .github/workflows/ci.yml no existe."
    ci_content = ci_workflow_path.read_text(encoding="utf-8-sig")

    assert "pytest" in ci_content, "El CI workflow debe ejecutar pytest."
    assert "backend/requirements.txt" in ci_content, "El CI workflow debe instalar requirements.txt."
    assert "shared-contracts/openapi.json" in ci_content, "El CI workflow debe validar sincronización de openapi.json."
    assert "docker compose config" in ci_content, "El CI workflow debe validar sintaxis de docker-compose."
    assert "init-schemas.sql" in ci_content, "El CI workflow debe validar el script de aislamiento multi-esquema."

    # 2. Android Client Network Models Parity
    api_models_path = MONOREPO_ROOT / "client-mobile" / "core" / "network" / "ApiModels.kt"
    assert api_models_path.exists(), "ApiModels.kt no existe."
    api_models_source = api_models_path.read_text(encoding="utf-8-sig")

    assert "data class ProductVariantDto" in api_models_source, "Falta ProductVariantDto en ApiModels.kt."
    assert "variantSku" in api_models_source, "Falta variantSku en ApiModels.kt."
    assert "variants: List<ProductVariantDto>" in api_models_source, "ProductResponseDto debe incluir lista de variantes."

    # 3. feat_shop Domain & Presentation Parity
    shop_domain_path = MONOREPO_ROOT / "client-mobile" / "features" / "feat_shop" / "domain" / "ShopDomain.kt"
    assert shop_domain_path.exists(), "ShopDomain.kt no existe."
    shop_domain_source = shop_domain_path.read_text(encoding="utf-8-sig")
    assert "ShopProductVariant" in shop_domain_source, "Falta ShopProductVariant en ShopDomain.kt."
    assert "variantSku" in shop_domain_source, "Falta variantSku en ShopDomain.kt."

    shop_presentation_path = MONOREPO_ROOT / "client-mobile" / "features" / "feat_shop" / "presentation" / "ShopPresentation.kt"
    assert shop_presentation_path.exists(), "ShopPresentation.kt no existe."
    shop_pres_source = shop_presentation_path.read_text(encoding="utf-8-sig")
    assert "VariantSelected" in shop_pres_source, "Falta evento VariantSelected en ShopPresentation.kt."
    assert "selectedVariantByProduct" in shop_pres_source, "ShopUiState debe incluir selectedVariantByProduct."
    assert "private val _uiState = MutableStateFlow" in shop_pres_source, "UDF: _uiState debe ser estrictamente privado."


def test_mobile_loyalty_and_refresh_contract_parity() -> None:
    """Verifies mobile Android contract parity for refresh tokens, VIP loyalty, and points redemption."""
    # 1. OpenAPI Contract Check
    assert OPENAPI_CONTRACT_PATH.exists(), "shared-contracts/openapi.json no existe."
    openapi_raw = OPENAPI_CONTRACT_PATH.read_text(encoding="utf-8")
    openapi = json.loads(openapi_raw)

    paths = openapi.get("paths", {})
    assert "/api/v1/identity/auth/refresh" in paths, "Falta endpoint /api/v1/identity/auth/refresh en OpenAPI."
    assert "/api/v1/wallet/me/redeem-points" in paths, "Falta endpoint /api/v1/wallet/me/redeem-points en OpenAPI."

    schemas = openapi.get("components", {}).get("schemas", {})
    wallet_summary = schemas.get("WalletSummaryResponse", {})
    props = wallet_summary.get("properties", {})
    assert "loyalty_tier" in props, "Falta loyalty_tier en WalletSummaryResponse."
    assert "loyalty_points" in props, "Falta loyalty_points en WalletSummaryResponse."

    # 2. Android Client Network Models & Service Parity
    api_models_path = MONOREPO_ROOT / "client-mobile" / "core" / "network" / "ApiModels.kt"
    assert api_models_path.exists(), "ApiModels.kt no existe."
    api_models_source = api_models_path.read_text(encoding="utf-8-sig")

    assert "data class RefreshTokenRequestDto" in api_models_source, "Falta RefreshTokenRequestDto en ApiModels.kt."
    assert "loyaltyTier" in api_models_source, "Falta loyaltyTier en ApiModels.kt."
    assert "loyaltyPoints" in api_models_source, "Falta loyaltyPoints en ApiModels.kt."
    assert "lifetimeVolumeCents" in api_models_source, "Falta lifetimeVolumeCents en ApiModels.kt."

    api_service_path = MONOREPO_ROOT / "client-mobile" / "core" / "network" / "SuperAppApiService.kt"
    assert api_service_path.exists(), "SuperAppApiService.kt no existe."
    api_service_source = api_service_path.read_text(encoding="utf-8-sig")

    assert "refreshTokens" in api_service_source, "Falta refreshTokens en SuperAppApiService.kt."
    assert "redeemLoyaltyPoints" in api_service_source, "Falta redeemLoyaltyPoints en SuperAppApiService.kt."

    # 3. feat_wallet Domain & Presentation Parity
    wallet_domain_path = MONOREPO_ROOT / "client-mobile" / "features" / "feat_wallet" / "domain" / "WalletDomain.kt"
    assert wallet_domain_path.exists(), "WalletDomain.kt no existe."
    wallet_domain_source = wallet_domain_path.read_text(encoding="utf-8-sig")
    assert "loyaltyTier" in wallet_domain_source, "Falta loyaltyTier en WalletDomain.kt."
    assert "loyaltyPoints" in wallet_domain_source, "Falta loyaltyPoints en WalletDomain.kt."
    assert "redeemLoyaltyPoints" in wallet_domain_source, "Falta redeemLoyaltyPoints en WalletFeatureRepository."

    wallet_pres_path = MONOREPO_ROOT / "client-mobile" / "features" / "feat_wallet" / "presentation" / "WalletPresentation.kt"
    assert wallet_pres_path.exists(), "WalletPresentation.kt no existe."
    wallet_pres_source = wallet_pres_path.read_text(encoding="utf-8-sig")
    assert "loyaltyTier" in wallet_pres_source, "WalletUiState debe exponer loyaltyTier."
    assert "loyaltyPoints" in wallet_pres_source, "WalletUiState debe exponer loyaltyPoints."
    assert "RedeemPointsClicked" in wallet_pres_source, "Falta RedeemPointsClicked en WalletUiEvent."
    assert "private val _uiState = MutableStateFlow" in wallet_pres_source, "UDF: _uiState debe ser estrictamente privado en WalletViewModel."

    # 4. feat_auth Domain & Presentation Parity
    auth_domain_path = MONOREPO_ROOT / "client-mobile" / "features" / "feat_auth" / "domain" / "AuthDomain.kt"
    assert auth_domain_path.exists(), "AuthDomain.kt no existe."
    auth_domain_source = auth_domain_path.read_text(encoding="utf-8-sig")
    assert "refreshToken" in auth_domain_source, "Falta refreshToken en AuthUserSession."
    assert "refresh" in auth_domain_source, "Falta refresh en AuthRepository."

    auth_pres_path = MONOREPO_ROOT / "client-mobile" / "features" / "feat_auth" / "presentation" / "AuthPresentation.kt"
    assert auth_pres_path.exists(), "AuthPresentation.kt no existe."
    auth_pres_source = auth_pres_path.read_text(encoding="utf-8-sig")
    assert "refreshToken" in auth_pres_source, "Falta refreshToken en AuthPresentation.kt."
    assert "RefreshSessionClicked" in auth_pres_source, "Falta RefreshSessionClicked en AuthUiEvent."
    assert "private val _uiState = MutableStateFlow" in auth_pres_source, "UDF: _uiState debe ser estrictamente privado en AuthViewModel."



@pytest.mark.asyncio
async def test_healthz_readyz_and_outbox_resilience() -> None:
    """Verifies production liveness/readiness probes (/healthz, /readyz), DB outage 503 handling,

    and transactional Outbox pattern resilience against event bus failures (monolitos.pdf).
    """
    from dataclasses import dataclass
    from unittest.mock import AsyncMock
    from httpx import ASGITransport, AsyncClient
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
    from sqlalchemy.pool import StaticPool

    from app.core.database import (
        Base,
        reset_session_factory,
        set_session_factory,
    )
    from app.core.event_bus import DomainEvent, InMemoryEventBus
    from app.core.outbox import (
        publish_event_with_outbox,
        relay_pending_outbox_events,
    )
    from app.main import app

    # 1. Setup isolated in-memory DB for outbox and readiness probe
    test_engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    test_factory = async_sessionmaker(
        bind=test_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )
    set_session_factory(test_factory)

    transport = ASGITransport(app=app)
    try:
        async with AsyncClient(transport=transport, base_url="http://testserver") as client:
            # 2. Test /healthz (Liveness: immediate 200 OK)
            res_healthz = await client.get("/healthz")
            assert res_healthz.status_code == 200
            assert res_healthz.json() == {"status": "ok"}

            # 3. Test /readyz (Readiness: live SELECT 1 -> 200 ready)
            res_readyz = await client.get("/readyz")
            assert res_readyz.status_code == 200
            assert res_readyz.json() == {"status": "ready"}

            # 4. Test /readyz failure under DB outage (returns 503 Service Unavailable)
            class BrokenSession:
                async def __aenter__(self) -> None:
                    raise RuntimeError("Database connection lost")

                async def __aexit__(self, *args: object) -> None:
                    pass

            class BrokenFactory:
                def __call__(self) -> BrokenSession:
                    return BrokenSession()

            set_session_factory(BrokenFactory())  # type: ignore[arg-type]
            res_readyz_fail = await client.get("/readyz")
            assert res_readyz_fail.status_code == 503
            assert res_readyz_fail.json()["status"] == "unhealthy"
            assert "Database connection lost" in res_readyz_fail.json()["error"]

            # Restore healthy factory
            set_session_factory(test_factory)

            # 5. Outbox Resilience: Successful dispatch
            @dataclass(frozen=True, kw_only=True)
            class OrderShippedDomainEvent(DomainEvent):
                tracking_number: str

            event = OrderShippedDomainEvent(tracking_number="TRACK-COL-9901")
            bus = InMemoryEventBus()

            async with test_factory() as session:
                entry = await publish_event_with_outbox(bus, event, session=session)
                await session.commit()

                assert entry.status == "PUBLISHED"
                assert entry.published_at is not None
                assert entry.error_message is None
                assert entry.event_name == "OrderShippedDomainEvent"
                assert "TRACK-COL-9901" in entry.payload

            # 6. Outbox Resilience: Broken bus does NOT crash the caller request loop
            broken_bus = AsyncMock()
            broken_bus.publish = AsyncMock(side_effect=RuntimeError("Redis stream buffer timeout"))

            async with test_factory() as session:
                failing_entry = await publish_event_with_outbox(
                    broken_bus, event, session=session
                )
                await session.commit()

                assert failing_entry.status == "FAILED"
                assert failing_entry.published_at is None
                assert "Redis stream buffer timeout" in (failing_entry.error_message or "")
                assert failing_entry.retry_count == 1

            # 7. Outbox Relay: Re-dispatches failed events once connectivity is restored
            async with test_factory() as session:
                dispatched = await relay_pending_outbox_events(bus, session=session)
                assert dispatched >= 1

    finally:
        reset_session_factory()
        await test_engine.dispose()


@pytest.mark.asyncio
async def test_outbox_background_retry_loop_lifecycle() -> None:
    """Verifies Outbox background worker startup, periodic relay execution,

    and clean cancellation without hanging or resource leaks (monolitos.pdf).
    """
    import asyncio
    from dataclasses import dataclass
    from unittest.mock import AsyncMock
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
    from sqlalchemy.pool import StaticPool
    from sqlalchemy import select

    from app.core.database import Base, reset_session_factory, set_session_factory
    from app.core.event_bus import DomainEvent, InMemoryEventBus
    from app.core.outbox import OutboxEventModel, publish_event_with_outbox, run_outbox_retry_loop
    from app.core.config import get_settings
    from app.main import app, lifespan

    # 1. Setup isolated in-memory DB for outbox
    test_engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    test_factory = async_sessionmaker(
        bind=test_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )
    set_session_factory(test_factory)

    try:
        # 2. Insert a failed outbox event
        @dataclass(frozen=True, kw_only=True)
        class StockReplenishedEvent(DomainEvent):
            product_sku: str
            units: int

        failed_event = StockReplenishedEvent(product_sku="DESK-PAD-PRO", units=10)
        broken_bus = AsyncMock()
        broken_bus.publish = AsyncMock(side_effect=RuntimeError("Simulated network timeout"))

        async with test_factory() as session:
            entry = await publish_event_with_outbox(broken_bus, failed_event, session=session)
            await session.commit()
            assert entry.status == "FAILED"
            assert entry.retry_count == 1

        # 3. Start background retry loop with a healthy bus and very short interval
        healthy_bus = InMemoryEventBus()
        worker_task = asyncio.create_task(
            run_outbox_retry_loop(
                event_bus=healthy_bus,
                session_factory=test_factory,
                interval_seconds=0.05,
            )
        )

        # Allow worker loop to execute at least one cycle
        await asyncio.sleep(0.15)

        # Verify event was relayed and marked as PUBLISHED
        async with test_factory() as session:
            stmt = select(OutboxEventModel).where(OutboxEventModel.id == entry.id)
            result = await session.execute(stmt)
            updated_entry = result.scalar_one()
            assert updated_entry.status == "PUBLISHED"
            assert updated_entry.published_at is not None

        # 4. Clean cancellation test: canceling the worker must not raise unhandled errors
        worker_task.cancel()
        try:
            await worker_task
        except asyncio.CancelledError:
            pass

        assert worker_task.done()

        # 5. Verify FastAPI lifespan integration with outbox_retry_worker_enabled
        from unittest.mock import patch
        with patch("app.main.ensure_sqlite_columns_up_to_date", new_callable=AsyncMock):
            settings = get_settings()
            original_enabled = settings.outbox_retry_worker_enabled
            original_interval = settings.outbox_retry_interval_seconds
            try:
                settings.outbox_retry_worker_enabled = True
                settings.outbox_retry_interval_seconds = 0.05
                async with lifespan(app):
                    # Worker is actively running during app lifespan
                    await asyncio.sleep(0.08)
                # Lifespan exited: task was cleanly cancelled in finally block
            finally:
                settings.outbox_retry_worker_enabled = original_enabled
                settings.outbox_retry_interval_seconds = original_interval


    finally:
        reset_session_factory()
        await test_engine.dispose()


@pytest.mark.asyncio
async def test_request_id_and_process_time_headers() -> None:
    """Verifies that all HTTP responses include X-Request-ID and X-Process-Time-Ms headers,

    generating unique IDs when absent and propagating caller-supplied IDs (observability).
    """
    from httpx import ASGITransport, AsyncClient
    from app.main import app

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        # 1. Request without X-Request-ID: app should generate a valid UUID4
        res1 = await client.get("/healthz")
        assert res1.status_code == 200
        assert "x-request-id" in res1.headers
        generated_id = res1.headers["x-request-id"]
        assert len(generated_id) >= 32  # UUID format

        assert "x-process-time-ms" in res1.headers
        latency = float(res1.headers["x-process-time-ms"])
        assert latency >= 0.0

        # 2. Request with custom X-Request-ID: app must propagate the exact ID
        custom_id = "custom-trace-uuid-2026-abc"
        res2 = await client.get("/healthz", headers={"X-Request-ID": custom_id})
        assert res2.status_code == 200
        assert res2.headers.get("x-request-id") == custom_id
        assert "x-process-time-ms" in res2.headers
        assert float(res2.headers["x-process-time-ms"]) >= 0.0


def test_mobile_catalog_search_and_category_parity() -> None:
    """Verifies OpenAPI and Android feat_shop parity for catalog search & category_tag filtering (Laws 1, 3, 4)."""
    # 1. OpenAPI contract check for GET /api/v1/commerce/products query parameters
    assert OPENAPI_CONTRACT_PATH.exists(), "shared-contracts/openapi.json no existe."
    openapi = json.loads(OPENAPI_CONTRACT_PATH.read_text(encoding="utf-8"))
    products_get = openapi.get("paths", {}).get("/api/v1/commerce/products", {}).get("get", {})
    param_names = {p.get("name") for p in products_get.get("parameters", [])}
    assert "search" in param_names, "Falta query param 'search' en GET /api/v1/commerce/products (OpenAPI)."
    assert "category_tag" in param_names, "Falta query param 'category_tag' en GET /api/v1/commerce/products (OpenAPI)."

    # 2. Retrofit SuperAppApiService parity
    api_service_path = MOBILE_DIR / "core" / "network" / "SuperAppApiService.kt"
    assert api_service_path.is_file(), "Falta SuperAppApiService.kt."
    api_source = api_service_path.read_text(encoding="utf-8-sig")
    assert '@Query("search") search: String? = null' in api_source
    assert '@Query("category_tag") categoryTag: String? = null' in api_source

    # 3. feat_shop domain purity (Law 3) and repository contract
    shop_domain_path = MOBILE_FEATURES_DIR / "feat_shop" / "domain" / "ShopDomain.kt"
    domain_source = shop_domain_path.read_text(encoding="utf-8-sig")
    assert "search: String? = null" in domain_source
    assert "categoryTag: String? = null" in domain_source
    for forbidden in FORBIDDEN_KOTLIN_DOMAIN_IMPORTS:
        assert f"import {forbidden}" not in domain_source, (
            f"Violación de Pureza de Dominio (Ley 3) en ShopDomain.kt: import {forbidden}"
        )

    # 4. feat_shop application & infrastructure propagation
    use_case_source = (
        MOBILE_FEATURES_DIR / "feat_shop" / "application" / "ShopCatalogAndOrderUseCase.kt"
    ).read_text(encoding="utf-8-sig")
    assert "suspend fun loadActiveCatalog(" in use_case_source
    assert "search: String? = null" in use_case_source
    assert "categoryTag: String? = null" in use_case_source

    repo_source = (
        MOBILE_FEATURES_DIR / "feat_shop" / "infrastructure" / "RemoteShopRepository.kt"
    ).read_text(encoding="utf-8-sig")
    assert "api.listProducts(" in repo_source
    assert "search = search" in repo_source
    assert "categoryTag = categoryTag" in repo_source

    # 5. feat_shop presentation UDF & isolation (Laws 1 & 4)
    pres_source = (
        MOBILE_FEATURES_DIR / "feat_shop" / "presentation" / "ShopPresentation.kt"
    ).read_text(encoding="utf-8-sig")
    assert "private val _uiState = MutableStateFlow(ShopUiState())" in pres_source
    assert "val uiState: StateFlow<ShopUiState> = _uiState.asStateFlow()" in pres_source
    assert "val searchQuery: String" in pres_source
    assert "val selectedCategoryTag: String?" in pres_source
    assert "data class SearchQueryChanged" in pres_source
    assert "data class CategoryTagSelected" in pres_source
    assert "MENSWEAR" in pres_source and "DESK_SETUP" in pres_source
    for other_feat in ("feat_auth", "feat_wallet", "feat_studio"):
        assert f"co.superapp.features.{other_feat}." not in pres_source, (
            f"Violación Ley 1 en ShopPresentation.kt: import cruzado desde {other_feat}"
        )


def test_mobile_studio_niche_and_attribution_parity() -> None:
    """Verifies OpenAPI and Android feat_studio parity for content niche filtering & sales attribution (Laws 1, 3, 4)."""
    # 1. OpenAPI contract check for ContentNiche and attribution fields
    assert OPENAPI_CONTRACT_PATH.exists(), "shared-contracts/openapi.json no existe."
    openapi = json.loads(OPENAPI_CONTRACT_PATH.read_text(encoding="utf-8"))
    schemas = openapi.get("components", {}).get("schemas", {})

    niche_enum = set(schemas.get("ContentNiche", {}).get("enum", []))
    expected_niches = {
        "DESK_SETUP_UGC",
        "RAP_CULTURE_VIRAL",
        "YOUTUBE_HIGHLIGHT_CLIP",
        "MENSWEAR_LOOKBOOK",
    }
    assert expected_niches.issubset(niche_enum), (
        f"Faltan nichos esperados en OpenAPI ContentNiche: {expected_niches - niche_enum}"
    )

    media_job_props = schemas.get("MediaJobResponse", {}).get("properties", {})
    assert "content_niche" in media_job_props

    sched_post_props = schemas.get("ScheduledPostResponse", {}).get("properties", {})
    assert "conversions_count" in sched_post_props
    assert "revenue_attributed_cents" in sched_post_props

    niche_metric_props = schemas.get("NichePerformanceMetricResponse", {}).get("properties", {})
    assert "content_niche" in niche_metric_props
    assert "conversions_count" in niche_metric_props
    assert "revenue_attributed_cents" in niche_metric_props

    # 2. feat_studio domain purity (Law 3) and attribution/niche fields
    domain_source = (
        MOBILE_FEATURES_DIR / "feat_studio" / "domain" / "StudioDomain.kt"
    ).read_text(encoding="utf-8-sig")
    for niche in expected_niches:
        assert niche in domain_source, f"Falta nicho '{niche}' en StudioDomain.kt."
    assert "val contentNiche:" in domain_source
    assert "val conversionsCount: Int" in domain_source
    assert "val revenueAttributedCents: Long" in domain_source
    for forbidden in FORBIDDEN_KOTLIN_DOMAIN_IMPORTS:
        assert f"import {forbidden}" not in domain_source, (
            f"Violación de Pureza de Dominio (Ley 3) en StudioDomain.kt: import {forbidden}"
        )

    # 3. feat_studio application & infrastructure schedule/analytics sync
    use_case_source = (
        MOBILE_FEATURES_DIR / "feat_studio" / "application" / "StudioJobsUseCase.kt"
    ).read_text(encoding="utf-8-sig")
    assert "suspend fun loadPublishingSchedule()" in use_case_source
    assert "suspend fun loadNichePerformanceAnalytics()" in use_case_source

    repo_source = (
        MOBILE_FEATURES_DIR / "feat_studio" / "infrastructure" / "RemoteStudioRepository.kt"
    ).read_text(encoding="utf-8-sig")
    assert "api.getPublishingSchedule()" in repo_source
    assert "conversionsCount = dto.conversionsCount" in repo_source
    assert "revenueAttributedCents = dto.revenueAttributedCents" in repo_source

    # 4. feat_studio presentation UDF & feature isolation (Laws 1 & 4)
    pres_source = (
        MOBILE_FEATURES_DIR / "feat_studio" / "presentation" / "StudioPresentation.kt"
    ).read_text(encoding="utf-8-sig")
    assert "private val _uiState = MutableStateFlow(StudioUiState())" in pres_source
    assert "val uiState: StateFlow<StudioUiState> = _uiState.asStateFlow()" in pres_source
    assert "val activeNicheFilter: StudioContentNiche?" in pres_source
    assert "data class NicheFilterSelected" in pres_source
    assert "val filteredJobs: List<StudioMediaJob>" in pres_source
    assert "conversionsCount" in pres_source
    assert "revenueAttributedCents" in pres_source
    for other_feat in ("feat_auth", "feat_wallet", "feat_shop"):
        assert f"co.superapp.features.{other_feat}." not in pres_source, (
            f"Violación Ley 1 en StudioPresentation.kt: import cruzado desde {other_feat}"
        )


def test_vercel_serverless_entrypoint_and_config(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verifies Vercel ASGI entrypoint, vercel.json routing, .env.vercel.example, and serverless settings."""
    import importlib.util
    from fastapi import FastAPI
    from app.core.config import Settings

    # 1. vercel.json contract (Vercel Functions + Rewrites) & root requirements.txt
    vercel_json_path = MONOREPO_ROOT / "vercel.json"
    assert vercel_json_path.is_file(), "Falta vercel.json en la raíz del monorepo."
    vercel_cfg = json.loads(vercel_json_path.read_text(encoding="utf-8"))
    functions = vercel_cfg.get("functions", {})
    rewrites = vercel_cfg.get("rewrites", [])
    assert "api/index.py" in functions, "vercel.json debe configurar functions['api/index.py']."
    assert "backend/**" in str(functions["api/index.py"].get("includeFiles", "")), (
        "vercel.json debe incluir backend/** en functions['api/index.py'].includeFiles."
    )
    assert any(
        r.get("source") == "/(.*)" and r.get("destination") in ("/api/index", "/api/index.py")
        for r in rewrites
    ), "vercel.json debe reescribir /(.*) hacia /api/index."

    root_reqs_path = MONOREPO_ROOT / "requirements.txt"
    assert root_reqs_path.is_file(), "Falta requirements.txt ligero en la raíz para Vercel."
    root_reqs = root_reqs_path.read_text(encoding="utf-8")
    assert "fastapi" in root_reqs and "sqlalchemy[asyncio]" in root_reqs

    # 2. ASGI entrypoint api/index.py exposes FastAPI app with key routes
    entrypoint_path = MONOREPO_ROOT / "api" / "index.py"
    assert entrypoint_path.is_file(), "Falta el entrypoint ASGI api/index.py."
    spec = importlib.util.spec_from_file_location("vercel_api_index", entrypoint_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    vercel_app = getattr(module, "app", None)
    assert isinstance(vercel_app, FastAPI), "api/index.py debe exportar 'app' (FastAPI)."

    openapi_paths = set(vercel_app.openapi().get("paths", {}).keys())
    direct_paths = {getattr(r, "path", "") for r in vercel_app.routes}
    route_paths = openapi_paths | direct_paths
    for required_path in ("/", "/dashboard", "/healthz", "/readyz", "/api/v1/commerce/products"):
        assert required_path in route_paths, (
            f"Falta la ruta '{required_path}' en el entrypoint ASGI de Vercel."
        )

    # 3. backend/.env.vercel.example template
    vercel_env_path = BACKEND_DIR / ".env.vercel.example"
    assert vercel_env_path.is_file(), "Falta backend/.env.vercel.example."
    vercel_env_text = vercel_env_path.read_text(encoding="utf-8")
    for required_key in (
        "DATABASE_URL=",
        "ALLOWED_HOSTS=",
        "JWT_SECRET_KEY=",
        "WEBHOOK_HMAC_SECRET=",
        "OUTBOX_RETRY_WORKER_ENABLED=false",
        "MEDIA_OUTPUTS_DIR=/tmp/media_outputs",
    ):
        assert required_key in vercel_env_text, (
            f"Falta '{required_key}' en backend/.env.vercel.example."
        )

    # 4. Serverless settings fallback behavior when VERCEL=1 without external DATABASE_URL
    monkeypatch.setenv("VERCEL", "1")
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("DATABASE_URL_OVERRIDE", raising=False)
    monkeypatch.delenv("MEDIA_OUTPUTS_DIR", raising=False)
    monkeypatch.setenv("OUTBOX_RETRY_WORKER_ENABLED", "true")

    serverless_settings = Settings(_env_file=None)
    assert serverless_settings.is_vercel is True
    assert serverless_settings.async_database_url == "sqlite+aiosqlite:////tmp/super_app_vercel.db"
    assert serverless_settings.effective_media_outputs_dir == Path("/tmp/media_outputs")
    assert serverless_settings.outbox_retry_worker_enabled is False

    # 5. Serverless settings prefer external PostgreSQL DATABASE_URL when configured (e.g. Neon/Supabase)
    monkeypatch.setenv(
        "DATABASE_URL",
        "postgresql://user:pass@ep-demo-pooler.us-east-2.aws.neon.tech/neondb?sslmode=require&channel_binding=require",
    )
    neon_settings = Settings(_env_file=None)
    assert neon_settings.async_database_url == (
        "postgresql+asyncpg://user:pass@ep-demo-pooler.us-east-2.aws.neon.tech/neondb?ssl=require"
    )


def test_mobile_network_production_base_url_configured() -> None:
    """Verifies Android client defaults to Vercel production URL with 30s timeouts and preserves Laws 1 & 3."""
    expected_prod_url = "https://backend-tau-three-31.vercel.app/"
    expected_local_url = "http://10.0.2.2:8000/"

    api_service_path = MOBILE_DIR / "core" / "network" / "SuperAppApiService.kt"
    api_client_path = MOBILE_DIR / "core" / "network" / "SuperAppApiClient.kt"
    main_activity_path = MOBILE_DIR / "app" / "MainActivity.kt"

    assert api_service_path.is_file(), "Falta SuperAppApiService.kt."
    assert api_client_path.is_file(), "Falta SuperAppApiClient.kt."
    assert main_activity_path.is_file(), "Falta MainActivity.kt."

    service_src = api_service_path.read_text(encoding="utf-8-sig")
    client_src = api_client_path.read_text(encoding="utf-8-sig")
    activity_src = main_activity_path.read_text(encoding="utf-8-sig")

    assert f'const val DEFAULT_PRODUCTION_BASE_URL: String = "{expected_prod_url}"' in service_src
    assert f'const val LOCAL_EMULATOR_BASE_URL: String = "{expected_local_url}"' in service_src

    assert "baseUrl: String = DEFAULT_PRODUCTION_BASE_URL" in client_src
    assert "const val DEFAULT_TIMEOUT_SECONDS: Long = 30L" in client_src
    assert ".connectTimeout(timeoutSeconds, TimeUnit.SECONDS)" in client_src
    assert ".readTimeout(timeoutSeconds, TimeUnit.SECONDS)" in client_src
    assert ".writeTimeout(timeoutSeconds, TimeUnit.SECONDS)" in client_src

    assert "SuperAppApiClient.create(" in activity_src

    # Verify Law 1 & Law 3: pure domain layers of all 4 mobile features have no network/Android imports
    for feat in ("feat_auth", "feat_wallet", "feat_shop", "feat_studio"):
        domain_dir = MOBILE_FEATURES_DIR / feat / "domain"
        for kt_file in domain_dir.glob("*.kt"):
            src = kt_file.read_text(encoding="utf-8-sig")
            assert "co.superapp.core.network" not in src, (
                f"Violación Ley 3 en {kt_file}: el dominio puro no puede importar core.network."
            )
            for forbidden in FORBIDDEN_KOTLIN_DOMAIN_IMPORTS:
                assert f"import {forbidden}" not in src, (
                    f"Violación Ley 3 en {kt_file}: import prohibido '{forbidden}'."
                )


@pytest.mark.asyncio
async def test_vercel_cron_outbox_relay_endpoint_and_security(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verifies protected Vercel Cron endpoint GET /api/v1/internal/outbox/relay, vercel.json crons, and OpenAPI isolation."""
    from datetime import UTC, datetime
    from uuid import uuid4
    from httpx import ASGITransport, AsyncClient
    from sqlalchemy import select
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
    from sqlalchemy.pool import StaticPool

    from app.core.config import get_settings
    from app.core.database import (
        Base,
        SQLITE_SCHEMA_TRANSLATE_MAP,
        reset_session_factory,
        set_session_factory,
    )
    from app.core.outbox import OutboxEventModel
    from app.main import app

    # 1. Verify vercel.json (root & backend/) declare the cron job
    for vj_path in (MONOREPO_ROOT / "vercel.json", BACKEND_DIR / "vercel.json"):
        assert vj_path.is_file(), f"Falta {vj_path}."
        cfg = json.loads(vj_path.read_text(encoding="utf-8"))
        crons = cfg.get("crons", [])
        assert any(
            c.get("path") == "/api/v1/internal/outbox/relay" and c.get("schedule")
            for c in crons
        ), f"{vj_path} debe declarar el cron /api/v1/internal/outbox/relay."

    # 2. Verify internal endpoint is excluded from public OpenAPI schema
    assert "/api/v1/internal/outbox/relay" not in app.openapi().get("paths", {})

    # 3. Prepare isolated SQLite DB with 1 PENDING and 1 FAILED Outbox event
    test_engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        execution_options={"schema_translate_map": SQLITE_SCHEMA_TRANSLATE_MAP},
    )
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    factory = async_sessionmaker(
        bind=test_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )
    set_session_factory(factory)

    try:
        async with factory() as session:
            session.add_all(
                [
                    OutboxEventModel(
                        id=uuid4(),
                        event_id=uuid4(),
                        event_name="CronPendingEvent",
                        payload='{"source": "cron_test_1"}',
                        status="PENDING",
                        retry_count=0,
                        created_at=datetime.now(UTC),
                    ),
                    OutboxEventModel(
                        id=uuid4(),
                        event_id=uuid4(),
                        event_name="CronFailedEvent",
                        payload='{"source": "cron_test_2"}',
                        status="FAILED",
                        retry_count=1,
                        error_message="Transient error",
                        created_at=datetime.now(UTC),
                    ),
                ]
            )
            await session.commit()

        settings = get_settings()
        original_cron_secret = settings.cron_secret
        try:
            # 4. When CRON_SECRET is unset -> 401
            settings.cron_secret = None
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://testserver") as client:
                res_unset = await client.get("/api/v1/internal/outbox/relay")
                assert res_unset.status_code == 401

                # 5. Configure CRON_SECRET; missing or invalid Bearer token -> 401
                settings.cron_secret = "super-secret-vercel-cron-2026"
                res_no_hdr = await client.get("/api/v1/internal/outbox/relay")
                assert res_no_hdr.status_code == 401

                res_wrong = await client.get(
                    "/api/v1/internal/outbox/relay",
                    headers={"Authorization": "Bearer wrong-token"},
                )
                assert res_wrong.status_code == 401

                # 6. Valid Bearer token -> 200 OK & drains both PENDING and FAILED events
                res_ok = await client.get(
                    "/api/v1/internal/outbox/relay",
                    headers={"Authorization": "Bearer super-secret-vercel-cron-2026"},
                )
                assert res_ok.status_code == 200
                body = res_ok.json()
                assert body["status"] == "ok"
                assert body["relayed_count"] == 2

            async with factory() as session:
                rows = (await session.execute(select(OutboxEventModel))).scalars().all()
                assert len(rows) == 2
                assert all(r.status == "PUBLISHED" and r.published_at is not None for r in rows)
        finally:
            settings.cron_secret = original_cron_secret
    finally:
        reset_session_factory()
        await test_engine.dispose()




