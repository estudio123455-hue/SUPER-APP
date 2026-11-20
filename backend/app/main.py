"""Entry point for the Super App Modular Monolith (FastAPI).

Production Deployment Guide:
- Reverse Proxy Security: When running behind a reverse proxy (Nginx, Traefik, AWS ALB, Cloudflare),
  start Uvicorn with:
      uvicorn app.main:app --host 0.0.0.0 --port 8000 --proxy-headers --forwarded-allow-ips='*'
  This ensures that client IP addresses and protocol schemes are securely propagated via X-Forwarded-*
  headers, preventing host spoofing while respecting TrustedHostMiddleware perimeter rules.
"""

import asyncio
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
import time
from typing import Any
from uuid import uuid4

from fastapi import FastAPI, Request, Response, status
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import RedirectResponse

from pydantic import BaseModel, ConfigDict
from sqlalchemy import text

from app.core.config import get_settings
from app.core.dashboard_ui import router as dashboard_router
from app.core.database import (
    MODULE_SCHEMAS,
    ensure_sqlite_columns_up_to_date,
    get_session_factory,
)
from app.core.event_bus import event_bus
from app.core.outbox import run_outbox_retry_loop

from app.modules.commerce.presentation.router import router as commerce_router
from app.modules.identity.presentation.router import router as identity_router
from app.modules.media_ai.application.handlers import register_media_ai_event_handlers
from app.modules.media_ai.presentation.router import router as media_ai_router
from app.modules.wallet.application.handlers import register_wallet_event_handlers
from app.modules.wallet.presentation.router import router as wallet_router

settings = get_settings()


class HealthResponse(BaseModel):
    """Pydantic v2 response schema for system health check."""

    model_config = ConfigDict(from_attributes=True)

    status: str
    service: str
    version: str
    environment: str
    isolated_schemas: list[str]


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncGenerator[None, None]:
    """Registers cross-module EventBus subscriptions on startup, ensures SQLite schema parity,

    and manages the resilient background Outbox retry worker when enabled.
    """
    register_wallet_event_handlers(event_bus)
    register_media_ai_event_handlers(event_bus)
    await ensure_sqlite_columns_up_to_date()

    outbox_task: asyncio.Task[None] | None = None
    if settings.outbox_retry_worker_enabled:
        outbox_task = asyncio.create_task(
            run_outbox_retry_loop(
                event_bus=event_bus,
                session_factory=get_session_factory(),
                interval_seconds=settings.outbox_retry_interval_seconds,
            )
        )

    try:
        yield
    finally:
        if outbox_task is not None and not outbox_task.done():
            outbox_task.cancel()
            try:
                await outbox_task
            except asyncio.CancelledError:
                pass



def create_app() -> FastAPI:
    """Assembles the FastAPI application, mounts module routers, and wires EventBus."""
    application = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        debug=settings.debug,
        lifespan=lifespan,
    )

    # Perimeter Security: Enforces HTTP Host header validation
    application.add_middleware(
        TrustedHostMiddleware,
        allowed_hosts=settings.allowed_hosts,
    )

    @application.middleware("http")
    async def request_observability_middleware(
        request: Request,
        call_next: Any,
    ) -> Response:
        """Observability middleware: tracks X-Request-ID and measures request latency in ms."""
        incoming_id = request.headers.get("X-Request-ID")
        request_id = incoming_id.strip() if incoming_id and incoming_id.strip() else str(uuid4())
        start_time = time.perf_counter()

        response: Response = await call_next(request)

        process_time_ms = (time.perf_counter() - start_time) * 1000.0
        response.headers["X-Request-ID"] = request_id
        response.headers["X-Process-Time-Ms"] = f"{process_time_ms:.2f}"
        return response


    register_wallet_event_handlers(event_bus)
    register_media_ai_event_handlers(event_bus)

    application.include_router(dashboard_router)
    application.include_router(identity_router)
    application.include_router(wallet_router)
    application.include_router(commerce_router)
    application.include_router(media_ai_router)

    @application.get("/", include_in_schema=False)
    @application.get("/api/index", include_in_schema=False)
    async def root_redirect() -> RedirectResponse:
        """Redirects root URL directly to the interactive Control Center dashboard."""
        return RedirectResponse(
            url="/dashboard",
            status_code=status.HTTP_307_TEMPORARY_REDIRECT,
        )

    @application.get("/health", response_model=HealthResponse, tags=["System"])
    async def health_check() -> HealthResponse:
        return HealthResponse(
            status="healthy",
            service=settings.app_name,
            version=settings.app_version,
            environment=settings.environment,
            isolated_schemas=list(MODULE_SCHEMAS.values()),
        )

    @application.get("/healthz", tags=["System"])
    async def healthz() -> dict[str, str]:
        """Liveness probe: verifies that the process is up and running."""
        return {"status": "ok"}

    @application.get("/readyz", tags=["System"])
    async def readyz(response: Response) -> dict[str, Any]:
        """Readiness probe: validates database connectivity with a live SELECT 1 query."""
        factory = get_session_factory()
        try:
            async with factory() as session:
                await session.execute(text("SELECT 1"))
            return {"status": "ready"}
        except Exception as exc:
            response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
            return {"status": "unhealthy", "error": str(exc)}

    return application


app = create_app()
