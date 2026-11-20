"""Public API contract for the wallet module (Law 1).

Other bounded contexts (e.g. commerce, media_ai) MUST ONLY import from this file
when querying or debiting a user's wallet.
"""

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.event_bus import event_bus
from app.modules.wallet.application.dtos import ProcessTransactionCommand
from app.modules.wallet.application.events import (
    WalletCreditedEvent,
    WalletDebitedEvent,
)
from app.modules.wallet.application.use_cases import (
    GetWalletBalanceUseCase,
    ProcessTransactionUseCase,
)
from app.modules.wallet.domain.entities import TransactionType
from app.modules.wallet.domain.exceptions import (
    DuplicateTransactionError,
    InsufficientFundsError,
    WalletDomainError,
    WalletLockedError,
    WalletNotFoundError,
)
from app.modules.wallet.infrastructure.repositories import SqlAlchemyWalletRepository


@dataclass(frozen=True, kw_only=True)
class WalletPublicDTO:
    """Immutable cross-module representation of a user's wallet."""

    id: UUID
    user_id: UUID
    currency: str
    balance_cents: int
    loyalty_tier: str = "BRONZE"
    loyalty_points: int = 0
    lifetime_volume_cents: int = 0
    is_locked: bool
    created_at: datetime


async def get_user_wallet(
    user_id: UUID,
    session: AsyncSession,
) -> WalletPublicDTO:
    """Public contract for other modules to inspect a user's wallet balance."""
    repository = SqlAlchemyWalletRepository(session)
    use_case = GetWalletBalanceUseCase(repository=repository)
    balance_dto = await use_case.execute(user_id=user_id, limit=0)
    w = balance_dto.wallet
    return WalletPublicDTO(
        id=w.id,
        user_id=w.user_id,
        currency=w.currency,
        balance_cents=w.balance_cents,
        loyalty_tier=w.loyalty_tier,
        loyalty_points=w.loyalty_points,
        lifetime_volume_cents=w.lifetime_volume_cents,
        is_locked=w.is_locked,
        created_at=w.created_at,
    )


async def get_user_loyalty_tier(
    user_id: UUID,
    session: AsyncSession | None = None,
) -> str:
    """Public contract returning user's VIP LoyaltyTier ('BRONZE', 'SILVER', 'GOLD')."""
    if session is not None:
        repository = SqlAlchemyWalletRepository(session)
        wallet = await repository.get_by_user_id(user_id)
        return wallet.loyalty_tier.value if wallet is not None else "BRONZE"

    from app.core.database import get_session_factory

    session_factory = get_session_factory()
    async with session_factory() as local_session:
        repository = SqlAlchemyWalletRepository(local_session)
        wallet = await repository.get_by_user_id(user_id)
        return wallet.loyalty_tier.value if wallet is not None else "BRONZE"


async def debit_user_wallet(
    user_id: UUID,
    amount_cents: int,
    reference: str,
    idempotency_key: str,
    session: AsyncSession,
) -> WalletPublicDTO:
    """Public contract for other modules (e.g. commerce) to charge a user's wallet."""
    repository = SqlAlchemyWalletRepository(session)
    use_case = ProcessTransactionUseCase(
        repository=repository,
        event_bus=event_bus,
    )
    wallet_dto, _ = await use_case.execute(
        ProcessTransactionCommand(
            user_id=user_id,
            amount_cents=amount_cents,
            transaction_type=TransactionType.DEBIT,
            reference=reference,
            idempotency_key=idempotency_key,
        )
    )
    return WalletPublicDTO(
        id=wallet_dto.id,
        user_id=wallet_dto.user_id,
        currency=wallet_dto.currency,
        balance_cents=wallet_dto.balance_cents,
        is_locked=wallet_dto.is_locked,
        created_at=wallet_dto.created_at,
    )


__all__ = [
    "DuplicateTransactionError",
    "InsufficientFundsError",
    "WalletCreditedEvent",
    "WalletDebitedEvent",
    "WalletDomainError",
    "WalletLockedError",
    "WalletNotFoundError",
    "WalletPublicDTO",
    "debit_user_wallet",
    "get_user_loyalty_tier",
    "get_user_wallet",
]
