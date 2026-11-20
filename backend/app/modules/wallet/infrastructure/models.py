"""SQLAlchemy 2.0 models for the Wallet module isolated in 'wallet_schema' (Law 2).

No ForeignKeys to identity_schema are permitted; user_id is stored as a pure indexed UUID.
"""

from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy import BigInteger, Boolean, DateTime, Integer, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import build_schema_base

WalletBase = build_schema_base("wallet")


class WalletModel(WalletBase):
    """Database representation of a User Wallet in wallet_schema."""

    __tablename__ = "wallets"

    id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )
    user_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        unique=True,
        index=True,
        nullable=False,
    )
    currency: Mapped[str] = mapped_column(
        String(3),
        nullable=False,
        default="COP",
    )
    balance_cents: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"),
        nullable=False,
        default=0,
    )
    loyalty_tier: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        default="BRONZE",
    )
    loyalty_points: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"),
        nullable=False,
        default=0,
    )
    lifetime_volume_cents: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"),
        nullable=False,
        default=0,
    )
    is_locked: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
    )


class LedgerEntryModel(WalletBase):
    """Database representation of an immutable accounting LedgerEntry in wallet_schema."""

    __tablename__ = "ledger_entries"

    id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )
    wallet_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        index=True,
        nullable=False,
    )
    amount_cents: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"),
        nullable=False,
    )
    transaction_type: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
    )
    status: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        default="COMPLETED",
    )
    reference: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    idempotency_key: Mapped[str] = mapped_column(
        String(128),
        unique=True,
        index=True,
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
    )
