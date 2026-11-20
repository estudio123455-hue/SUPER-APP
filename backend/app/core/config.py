"""Global application settings powered by pydantic-settings."""

from functools import lru_cache
import os
from pathlib import Path
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Typed configuration for the Super App Modular Monolith."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # App Info
    app_name: str = Field(default="Super App Ecosystem API")
    app_version: str = Field(default="0.1.0")
    environment: str = Field(default="development")
    debug: bool = Field(default=True)

    # Database Configuration (defaults to persistent local SQLite when Postgres is not enabled)
    use_postgres: bool = Field(default=False)
    sqlite_db_path: str = Field(default="sqlite+aiosqlite:///./super_app_dev.db")
    postgres_user: str = Field(default="postgres")
    postgres_password: str = Field(default="postgres")
    postgres_host: str = Field(default="localhost")
    postgres_port: int = Field(default=5432)
    postgres_db: str = Field(default="super_app_db")
    database_url: str | None = Field(default=None)
    database_url_override: str | None = Field(default=None)

    # JWT Security Configuration
    jwt_secret_key: str = Field(default="CHANGE_ME_IN_PRODUCTION_SUPER_SECRET_KEY")
    jwt_algorithm: str = Field(default="HS256")
    jwt_access_token_expire_minutes: int = Field(default=30)
    jwt_refresh_token_expire_days: int = Field(default=7)

    # Distributed Event Bus / Cache & Payment Gateway Webhook HMAC
    redis_url: str = Field(default="redis://localhost:6379/0")
    payment_webhook_secret: str = Field(
        default="CHANGE_ME_IN_PRODUCTION_WEBHOOK_HMAC_SECRET"
    )

    # Perimeter Security / Trusted Hosts
    allowed_hosts: list[str] = Field(default_factory=lambda: ["*"])

    # Transactional Outbox Background Worker (Operational Resilience)
    outbox_retry_worker_enabled: bool = Field(default=False)
    outbox_retry_interval_seconds: float = Field(default=15.0)

    # Media AI Physical Artifacts Directory
    media_outputs_dir: str | None = Field(default=None)

    def model_post_init(self, __context: object) -> None:
        if self.is_vercel:
            # Serverless functions must not spawn infinite background retry loops
            object.__setattr__(self, "outbox_retry_worker_enabled", False)

    @property
    def is_vercel(self) -> bool:
        """Returns True when running inside Vercel Serverless Functions."""
        return bool(os.getenv("VERCEL") or os.getenv("VERCEL_ENV"))

    @property
    def effective_media_outputs_dir(self) -> Path:
        """Returns a writable artifacts directory (defaults to /tmp/media_outputs on Vercel)."""
        if self.media_outputs_dir and self.media_outputs_dir.strip():
            return Path(self.media_outputs_dir.strip())
        if self.is_vercel:
            return Path("/tmp/media_outputs")
        return Path(__file__).resolve().parents[2] / "media_outputs"

    @property
    def async_database_url(self) -> str:
        """Builds the SQLAlchemy 2.0 async connection URI (local SQLite, Vercel /tmp SQLite, or PostgreSQL)."""
        if self.database_url_override and self.database_url_override.strip():
            return self.database_url_override.strip()
        if self.database_url and self.database_url.strip():
            raw_url = self.database_url.strip()
            if raw_url.startswith("postgres://"):
                return raw_url.replace("postgres://", "postgresql+asyncpg://", 1)
            if raw_url.startswith("postgresql://"):
                return raw_url.replace("postgresql://", "postgresql+asyncpg://", 1)
            return raw_url
        if self.use_postgres:
            return (
                f"postgresql+asyncpg://{self.postgres_user}:{self.postgres_password}"
                f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
            )
        if self.is_vercel:
            return "sqlite+aiosqlite:////tmp/super_app_vercel.db"
        return self.sqlite_db_path


@lru_cache
def get_settings() -> Settings:
    """Returns a cached singleton of application settings."""
    return Settings()
