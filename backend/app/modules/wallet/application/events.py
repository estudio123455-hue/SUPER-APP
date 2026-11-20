"""Domain events emitted by the Wallet bounded context."""

from dataclasses import dataclass
from uuid import UUID

from app.core.event_bus import DomainEvent


@dataclass(frozen=True, kw_only=True)
class WalletCreditedEvent(DomainEvent):
    """Published when funds are credited to a user's wallet."""

    wallet_id: UUID
    user_id: UUID
    amount_cents: int
    new_balance_cents: int
    currency: str
    reference: str
    idempotency_key: str


@dataclass(frozen=True, kw_only=True)
class WalletDebitedEvent(DomainEvent):
    """Published when funds are debited from a user's wallet."""

    wallet_id: UUID
    user_id: UUID
    amount_cents: int
    new_balance_cents: int
    currency: str
    reference: str
    idempotency_key: str
