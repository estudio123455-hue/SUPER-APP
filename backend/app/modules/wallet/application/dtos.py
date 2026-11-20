"""Application commands and DTOs for the Wallet module."""

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from app.modules.wallet.domain.entities import (
    LedgerEntry,
    TransactionStatus,
    TransactionType,
    Wallet,
)


@dataclass(frozen=True, kw_only=True)
class CreateWalletCommand:
    """Command to create an initial wallet for a user."""

    user_id: UUID
    currency: str = "COP"


@dataclass(frozen=True, kw_only=True)
class ProcessTransactionCommand:
    """Command to credit or debit a user's wallet idempotently."""

    user_id: UUID
    amount_cents: int
    transaction_type: TransactionType
    reference: str
    idempotency_key: str


@dataclass(frozen=True, kw_only=True)
class ProcessPaymentWebhookCommand:
    """Command to credit a user's wallet from an authenticated Payment Gateway Webhook."""

    event_id: str
    user_id: UUID
    amount_cents: int
    provider: str
    currency: str = "COP"


@dataclass(frozen=True, kw_only=True)
class LedgerEntryDTO:
    """Application DTO representing a single ledger movement."""

    id: UUID
    wallet_id: UUID
    amount_cents: int
    transaction_type: TransactionType
    status: TransactionStatus
    reference: str
    idempotency_key: str
    created_at: datetime

    @classmethod
    def from_entity(cls, entry: LedgerEntry) -> "LedgerEntryDTO":
        return cls(
            id=entry.id,
            wallet_id=entry.wallet_id,
            amount_cents=entry.amount_cents,
            transaction_type=entry.transaction_type,
            status=entry.status,
            reference=entry.reference,
            idempotency_key=entry.idempotency_key,
            created_at=entry.created_at,
        )


@dataclass(frozen=True, kw_only=True)
class WalletDTO:
    """Application DTO representing a user's wallet state."""

    id: UUID
    user_id: UUID
    currency: str
    balance_cents: int
    loyalty_tier: str = "BRONZE"
    loyalty_points: int = 0
    lifetime_volume_cents: int = 0
    is_locked: bool
    created_at: datetime

    @classmethod
    def from_entity(cls, wallet: Wallet) -> "WalletDTO":
        return cls(
            id=wallet.id,
            user_id=wallet.user_id,
            currency=wallet.currency,
            balance_cents=wallet.balance_cents,
            loyalty_tier=wallet.loyalty_tier.value,
            loyalty_points=wallet.loyalty_points,
            lifetime_volume_cents=wallet.lifetime_volume_cents,
            is_locked=wallet.is_locked,
            created_at=wallet.created_at,
        )


@dataclass(frozen=True, kw_only=True)
class WalletBalanceDTO:
    """Application DTO bundling wallet summary and its recent ledger movements."""

    wallet: WalletDTO
    recent_entries: tuple[LedgerEntryDTO, ...]


@dataclass(frozen=True, kw_only=True)
class PaymentWebhookResultDTO:
    """Application DTO returned after processing an idempotent payment gateway webhook."""

    wallet: WalletDTO
    entry: LedgerEntryDTO
    provider: str
    already_processed: bool
