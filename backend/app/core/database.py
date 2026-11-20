"""SQLAlchemy 2.0 async database setup with schema-per-module isolation (Law 2)."""

from collections.abc import AsyncGenerator
from typing import Any, Final

from sqlalchemy import MetaData
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from app.core.config import get_settings

# Bounded Context PostgreSQL Schemas (Law 2: Database Isolation by Schema)
MODULE_SCHEMAS: Final[dict[str, str]] = {
    "identity": "identity_schema",
    "media_ai": "media_ai_schema",
    "commerce": "commerce_schema",
    "wallet": "wallet_schema",
}

# Schema translation map for engines that do not use PostgreSQL schemas (e.g. SQLite dev/tests)
SQLITE_SCHEMA_TRANSLATE_MAP: Final[dict[str | None, str | None]] = {
    schema: None for schema in MODULE_SCHEMAS.values()
}

NAMING_CONVENTION: Final[dict[str, str]] = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    """Base declarative class for SQLAlchemy 2.0 models."""

    metadata = MetaData(naming_convention=NAMING_CONVENTION)


def build_schema_base(module_name: str) -> type[DeclarativeBase]:
    """Creates a module-scoped DeclarativeBase bound to its dedicated PostgreSQL schema."""
    if module_name not in MODULE_SCHEMAS:
        raise ValueError(
            f"Unknown module '{module_name}'. Allowed modules: {list(MODULE_SCHEMAS.keys())}"
        )

    schema_name = MODULE_SCHEMAS[module_name]
    module_metadata = MetaData(
        schema=schema_name,
        naming_convention=NAMING_CONVENTION,
    )

    class ModuleScopedBase(DeclarativeBase):
        metadata = module_metadata

    ModuleScopedBase.__name__ = f"{module_name.title().replace('_', '')}Base"
    return ModuleScopedBase


settings = get_settings()

_engine_kwargs: dict[str, Any] = {
    "echo": False,
    "future": True,
}

# Production pool hygiene: pool_pre_ping discards stale/closed connections,
# and pool_recycle recycles connections after 30 minutes (1800s).
# In-memory SQLite (StaticPool) does not support connection pooling or recycling.
if ":memory:" not in settings.async_database_url:
    _engine_kwargs["pool_pre_ping"] = True
    _engine_kwargs["pool_recycle"] = 1800

if settings.async_database_url.startswith("sqlite"):
    _engine_kwargs["execution_options"] = {
        "schema_translate_map": SQLITE_SCHEMA_TRANSLATE_MAP
    }
    if settings.is_vercel and ":memory:" not in settings.async_database_url:
        _engine_kwargs["connect_args"] = {"check_same_thread": False}

engine: AsyncEngine = create_async_engine(
    settings.async_database_url,
    **_engine_kwargs,
)

AsyncSessionLocal: async_sessionmaker[AsyncSession] = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)

_active_session_factory: async_sessionmaker[AsyncSession] = AsyncSessionLocal


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    """Returns the current async_sessionmaker (used by HTTP requests and EventBus handlers)."""
    return _active_session_factory


def set_session_factory(factory: async_sessionmaker[AsyncSession]) -> None:
    """Overrides the active session factory (useful for isolated integration tests)."""
    global _active_session_factory
    _active_session_factory = factory


def reset_session_factory() -> None:
    """Restores the default AsyncSessionLocal factory."""
    global _active_session_factory
    _active_session_factory = AsyncSessionLocal


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency providing an isolated AsyncSession per request."""
    factory = get_session_factory()
    async with factory() as session:
        yield session


async def ensure_sqlite_columns_up_to_date(target_engine: AsyncEngine | None = None) -> None:
    """Idempotently adds missing columns to existing SQLite tables based on SQLAlchemy metadata.

    Guarantees local development SQLite databases smoothly inherit newly added entity columns
    without throwing 500 OperationalErrors or requiring manual database deletion.
    """
    engine_to_use = target_engine or engine

    def _sync_upgrade(conn: Any) -> None:
        from app.modules.commerce.infrastructure.models import CommerceBase
        from app.modules.identity.infrastructure.models import IdentityBase
        from app.modules.media_ai.infrastructure.models import MediaAiBase
        from app.modules.wallet.infrastructure.models import WalletBase

        bases = (Base, IdentityBase, WalletBase, CommerceBase, MediaAiBase)

        if conn.dialect.name == "postgresql":
            for schema_name in MODULE_SCHEMAS.values():
                conn.exec_driver_sql(f'CREATE SCHEMA IF NOT EXISTS "{schema_name}"')
            for b in bases:
                b.metadata.create_all(conn)
            return

        if conn.dialect.name != "sqlite":
            return

        for b in bases:
            b.metadata.create_all(conn)

        for b in bases:
            for table in b.metadata.tables.values():
                table_name = table.name
                cursor = conn.exec_driver_sql(f"PRAGMA table_info('{table_name}')")
                existing_cols = {row[1] for row in cursor.fetchall()}
                if not existing_cols:
                    continue

                for col in table.columns:
                    if col.name not in existing_cols:
                        col_type = col.type.compile(dialect=conn.dialect)
                        default_clause = ""
                        if col.server_default is not None and hasattr(col.server_default, "arg"):
                            default_clause = f" DEFAULT {col.server_default.arg}"
                        elif col.default is not None and getattr(col.default, "is_scalar", False):
                            arg = col.default.arg
                            default_clause = (
                                f" DEFAULT '{arg}'"
                                if isinstance(arg, str)
                                else f" DEFAULT {arg}"
                            )
                        elif col.name in ("category_tag",):
                            default_clause = " DEFAULT 'GENERAL'"
                        elif col.name in ("loyalty_tier",):
                            default_clause = " DEFAULT 'BRONZE'"
                        elif col.name in (
                            "discount_cents",
                            "unit_cost_cents",
                            "stock_quantity",
                            "shipping_cost_cents",
                            "total_cogs_cents",
                            "net_profit_cents",
                            "subtotal_cents",
                            "loyalty_points",
                            "lifetime_volume_cents",
                        ):
                            default_clause = " DEFAULT 0"
                        elif col.name in ("use_real_pipeline",):
                            default_clause = " DEFAULT 0"
                        elif col.name in ("burn_subtitles", "is_active"):
                            default_clause = " DEFAULT 1"

                        conn.exec_driver_sql(
                            f"ALTER TABLE {table_name} ADD COLUMN {col.name} {col_type}{default_clause}"
                        )

    async with engine_to_use.begin() as connection:
        await connection.run_sync(_sync_upgrade)
