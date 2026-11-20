"""SQLAlchemy 2.0 implementation of WalletRepository with atomic ledger commits."""

from datetime import UTC
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.wallet.domain.entities import (
    LedgerEntry,
    LoyaltyTier,
    TransactionStatus,
    TransactionType,
    Wallet,
)
from app.modules.wallet.domain.exceptions import (
    DuplicateTransactionError,
    WalletNotFoundError,
)
from app.modules.wallet.domain.repositories import WalletRepository
from app.modules.wallet.infrastructure.models import LedgerEntryModel, WalletModel


class SqlAlchemyWalletRepository(WalletRepository):
    """Adapter persisting Wallets and LedgerEntries via SQLAlchemy 2.0 AsyncSession."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    @staticmethod
    def _to_wallet_domain(model: WalletModel) -> Wallet:
        created_at = model.created_at
        if created_at.tzinfo is None:
            created_at = created_at.replace(tzinfo=UTC)
        return Wallet(
            id=model.id,
            user_id=model.user_id,
            currency=model.currency,
            balance_cents=int(model.balance_cents),
            loyalty_tier=LoyaltyTier(model.loyalty_tier or "BRONZE"),
            loyalty_points=int(model.loyalty_points or 0),
            lifetime_volume_cents=int(model.lifetime_volume_cents or 0),
            is_locked=model.is_locked,
            created_at=created_at,
        )

    @staticmethod
    def _to_ledger_domain(model: LedgerEntryModel) -> LedgerEntry:
        created_at = model.created_at
        if created_at.tzinfo is None:
            created_at = created_at.replace(tzinfo=UTC)
        return LedgerEntry(
            id=model.id,
            wallet_id=model.wallet_id,
            amount_cents=int(model.amount_cents),
            transaction_type=TransactionType(model.transaction_type),
            status=TransactionStatus(model.status),
            reference=model.reference,
            idempotency_key=model.idempotency_key,
            created_at=created_at,
        )

    async def get_by_user_id(self, user_id: UUID) -> Wallet | None:
        stmt = (
            select(WalletModel)
            .where(WalletModel.user_id == user_id)
            .execution_options(populate_existing=True)
        )
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        return self._to_wallet_domain(model) if model is not None else None

    async def save(self, wallet: Wallet) -> Wallet:
        stmt = select(WalletModel).where(WalletModel.id == wallet.id)
        result = await self._session.execute(stmt)
        existing = result.scalar_one_or_none()

        if existing is None:
            model = WalletModel(
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
            self._session.add(model)
        else:
            existing.currency = wallet.currency
            existing.balance_cents = wallet.balance_cents
            existing.loyalty_tier = wallet.loyalty_tier.value
            existing.loyalty_points = wallet.loyalty_points
            existing.lifetime_volume_cents = wallet.lifetime_volume_cents
            existing.is_locked = wallet.is_locked
            model = existing

        await self._session.commit()
        return wallet

    async def add_ledger_entry(
        self,
        wallet: Wallet,
        entry: LedgerEntry,
    ) -> tuple[Wallet, LedgerEntry]:
        stmt = (
            select(WalletModel)
            .where(WalletModel.id == wallet.id)
            .execution_options(populate_existing=True)
        )
        result = await self._session.execute(stmt)
        wallet_model = result.scalar_one_or_none()
        if wallet_model is None:
            raise WalletNotFoundError(str(wallet.id))

        wallet_model.balance_cents = wallet.balance_cents
        wallet_model.loyalty_tier = wallet.loyalty_tier.value
        wallet_model.loyalty_points = wallet.loyalty_points
        wallet_model.lifetime_volume_cents = wallet.lifetime_volume_cents
        wallet_model.is_locked = wallet.is_locked

        entry_model = LedgerEntryModel(
            id=entry.id,
            wallet_id=entry.wallet_id,
            amount_cents=entry.amount_cents,
            transaction_type=entry.transaction_type.value,
            status=entry.status.value,
            reference=entry.reference,
            idempotency_key=entry.idempotency_key,
            created_at=entry.created_at,
        )
        self._session.add(entry_model)

        try:
            await self._session.commit()
        except IntegrityError as exc:
            await self._session.rollback()
            raise DuplicateTransactionError(entry.idempotency_key) from exc

        return (
            wallet,
            entry,
        )

    async def get_ledger_by_key(self, idempotency_key: str) -> LedgerEntry | None:
        stmt = select(LedgerEntryModel).where(
            LedgerEntryModel.idempotency_key == idempotency_key.strip()
        )
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        return self._to_ledger_domain(model) if model is not None else None

    async def list_entries(
        self,
        wallet_id: UUID,
        limit: int = 20,
    ) -> list[LedgerEntry]:
        stmt = (
            select(LedgerEntryModel)
            .where(LedgerEntryModel.wallet_id == wallet_id)
            .order_by(LedgerEntryModel.created_at.desc())
            .limit(limit)
        )
        result = await self._session.execute(stmt)
        models = result.scalars().all()
        return [self._to_ledger_domain(m) for m in models]
