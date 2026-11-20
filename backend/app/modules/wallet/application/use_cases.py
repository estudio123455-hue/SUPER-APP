"""Application Use Cases for the Wallet bounded context (Layer 2)."""

import asyncio
from uuid import UUID

from app.core.event_bus import InMemoryEventBus
from app.modules.wallet.application.dtos import (
    CreateWalletCommand,
    LedgerEntryDTO,
    PaymentWebhookResultDTO,
    ProcessPaymentWebhookCommand,
    ProcessTransactionCommand,
    WalletBalanceDTO,
    WalletDTO,
)
from app.modules.wallet.application.events import (
    WalletCreditedEvent,
    WalletDebitedEvent,
)
from app.modules.wallet.domain.entities import TransactionType, Wallet
from app.modules.wallet.domain.exceptions import (
    DuplicateTransactionError,
    WalletNotFoundError,
)
from app.modules.wallet.domain.repositories import WalletRepository


class CreateWalletUseCase:
    """Creates a wallet for a user idempotently (returns existing if already present)."""

    def __init__(self, repository: WalletRepository) -> None:
        self._repository = repository

    async def execute(self, command: CreateWalletCommand) -> WalletDTO:
        existing = await self._repository.get_by_user_id(command.user_id)
        if existing is not None:
            return WalletDTO.from_entity(existing)

        wallet = Wallet(
            user_id=command.user_id,
            currency=command.currency,
            balance_cents=0,
        )
        saved = await self._repository.save(wallet)
        return WalletDTO.from_entity(saved)


class GetWalletBalanceUseCase:
    """Retrieves a user's wallet balance and latest ledger entries."""

    def __init__(self, repository: WalletRepository) -> None:
        self._repository = repository

    async def execute(self, user_id: UUID, limit: int = 20) -> WalletBalanceDTO:
        wallet = await self._repository.get_by_user_id(user_id)
        if wallet is None:
            raise WalletNotFoundError(str(user_id))

        entries = await self._repository.list_entries(wallet.id, limit=limit)
        return WalletBalanceDTO(
            wallet=WalletDTO.from_entity(wallet),
            recent_entries=tuple(LedgerEntryDTO.from_entity(e) for e in entries),
        )


_WALLET_TRANSACTION_LOCK: asyncio.Lock = asyncio.Lock()


class ProcessTransactionUseCase:
    """Executes an atomic credit or debit with idempotency protection."""

    def __init__(
        self,
        repository: WalletRepository,
        event_bus: InMemoryEventBus,
    ) -> None:
        self._repository = repository
        self._event_bus = event_bus

    async def execute(
        self,
        command: ProcessTransactionCommand,
    ) -> tuple[WalletDTO, LedgerEntryDTO]:
        async with _WALLET_TRANSACTION_LOCK:
            if hasattr(self._repository, "_session"):
                self._repository._session.expire_all()

            normalized_key = command.idempotency_key.strip()
            if not normalized_key:
                raise ValueError("idempotency_key cannot be empty.")

            existing_entry = await self._repository.get_ledger_by_key(normalized_key)
            if existing_entry is not None:
                raise DuplicateTransactionError(normalized_key)

            wallet = await self._repository.get_by_user_id(command.user_id)
            if wallet is None:
                raise WalletNotFoundError(str(command.user_id))

            if command.transaction_type == TransactionType.CREDIT:
                updated_wallet, entry = wallet.credit(
                    amount_cents=command.amount_cents,
                    reference=command.reference,
                    idempotency_key=normalized_key,
                )
            elif command.transaction_type == TransactionType.DEBIT:
                updated_wallet, entry = wallet.debit(
                    amount_cents=command.amount_cents,
                    reference=command.reference,
                    idempotency_key=normalized_key,
                )
            else:
                raise ValueError(f"Unsupported transaction_type: {command.transaction_type}")

            saved_wallet, saved_entry = await self._repository.add_ledger_entry(
                updated_wallet,
                entry,
            )

            if command.transaction_type == TransactionType.CREDIT:
                await self._event_bus.publish(
                    WalletCreditedEvent(
                        wallet_id=saved_wallet.id,
                        user_id=saved_wallet.user_id,
                        amount_cents=saved_entry.amount_cents,
                        new_balance_cents=saved_wallet.balance_cents,
                        currency=saved_wallet.currency,
                        reference=saved_entry.reference,
                        idempotency_key=saved_entry.idempotency_key,
                    )
                )
            else:
                await self._event_bus.publish(
                    WalletDebitedEvent(
                        wallet_id=saved_wallet.id,
                        user_id=saved_wallet.user_id,
                        amount_cents=saved_entry.amount_cents,
                        new_balance_cents=saved_wallet.balance_cents,
                        currency=saved_wallet.currency,
                        reference=saved_entry.reference,
                        idempotency_key=saved_entry.idempotency_key,
                    )
                )

            return (
                WalletDTO.from_entity(saved_wallet),
                LedgerEntryDTO.from_entity(saved_entry),
            )


class ProcessPaymentGatewayWebhookUseCase:
    """Idempotently credits a user's wallet from a verified payment gateway notification (Nequi/PSE/Wompi)."""

    def __init__(
        self,
        repository: WalletRepository,
        event_bus: InMemoryEventBus,
    ) -> None:
        self._repository = repository
        self._event_bus = event_bus

    async def execute(
        self,
        command: ProcessPaymentWebhookCommand,
    ) -> PaymentWebhookResultDTO:
        normalized_event_id = command.event_id.strip()
        if not normalized_event_id:
            raise ValueError("Webhook event_id cannot be empty.")

        normalized_provider = command.provider.strip().upper() or "GATEWAY"

        wallet = await self._repository.get_by_user_id(command.user_id)
        if wallet is None:
            wallet = await self._repository.save(
                Wallet(
                    user_id=command.user_id,
                    currency=command.currency,
                    balance_cents=0,
                )
            )

        existing_entry = await self._repository.get_ledger_by_key(normalized_event_id)
        if existing_entry is not None:
            return PaymentWebhookResultDTO(
                wallet=WalletDTO.from_entity(wallet),
                entry=LedgerEntryDTO.from_entity(existing_entry),
                provider=normalized_provider,
                already_processed=True,
            )

        updated_wallet, entry = wallet.credit(
            amount_cents=command.amount_cents,
            reference=f"Recarga {normalized_provider} ({normalized_event_id})",
            idempotency_key=normalized_event_id,
        )
        saved_wallet, saved_entry = await self._repository.add_ledger_entry(
            updated_wallet,
            entry,
        )

        await self._event_bus.publish(
            WalletCreditedEvent(
                wallet_id=saved_wallet.id,
                user_id=saved_wallet.user_id,
                amount_cents=saved_entry.amount_cents,
                new_balance_cents=saved_wallet.balance_cents,
                currency=saved_wallet.currency,
                reference=saved_entry.reference,
                idempotency_key=saved_entry.idempotency_key,
            )
        )

        return PaymentWebhookResultDTO(
            wallet=WalletDTO.from_entity(saved_wallet),
            entry=LedgerEntryDTO.from_entity(saved_entry),
            provider=normalized_provider,
            already_processed=False,
        )


class CreditCashbackUseCase:
    """Credits 3% cashback points and updates VIP tier upon order delivery."""

    def __init__(
        self,
        repository: WalletRepository,
        event_bus: InMemoryEventBus,
    ) -> None:
        self._repository = repository
        self._event_bus = event_bus

    async def execute(
        self,
        buyer_id: UUID,
        order_id: UUID,
        gross_total_cents: int,
        cashback_rate: float = 0.03,
    ) -> WalletDTO | None:
        if gross_total_cents <= 0:
            return None

        idempotency_key = f"cashback-{order_id}"
        existing_entry = await self._repository.get_ledger_by_key(idempotency_key)
        if existing_entry is not None:
            wallet = await self._repository.get_by_user_id(buyer_id)
            return WalletDTO.from_entity(wallet) if wallet else None

        wallet = await self._repository.get_by_user_id(buyer_id)
        if wallet is None:
            wallet = await self._repository.save(
                Wallet(user_id=buyer_id, currency="COP", balance_cents=0)
            )

        updated_wallet = wallet.credit_cashback_and_upgrade_tier(
            order_gross_cents=gross_total_cents,
            cashback_rate=cashback_rate,
        )
        cashback_pts = int(gross_total_cents * cashback_rate)
        if cashback_pts <= 0:
            cashback_pts = 1

        from app.modules.wallet.domain.entities import (
            LedgerEntry,
            TransactionStatus,
            TransactionType,
        )

        entry = LedgerEntry(
            wallet_id=updated_wallet.id,
            amount_cents=cashback_pts,
            transaction_type=TransactionType.CREDIT,
            status=TransactionStatus.COMPLETED,
            reference=f"Puntos Cashback 3% #{str(order_id)[:8]}",
            idempotency_key=idempotency_key,
        )
        saved_wallet, _ = await self._repository.add_ledger_entry(
            updated_wallet,
            entry,
        )
        return WalletDTO.from_entity(saved_wallet)


class RedeemLoyaltyPointsUseCase:
    """Converts accumulated loyalty points directly into liquid balance_cents in COP."""

    def __init__(
        self,
        repository: WalletRepository,
        event_bus: InMemoryEventBus,
    ) -> None:
        self._repository = repository
        self._event_bus = event_bus

    async def execute(
        self,
        user_id: UUID,
        idempotency_key: str | None = None,
    ) -> tuple[WalletDTO, LedgerEntryDTO]:
        wallet = await self._repository.get_by_user_id(user_id)
        if wallet is None:
            raise WalletNotFoundError(str(user_id))

        if wallet.loyalty_points <= 0:
            raise ValueError("No hay puntos de fidelización disponibles para canjear.")

        from uuid import uuid4

        norm_key = (
            idempotency_key.strip()
            if idempotency_key and idempotency_key.strip()
            else f"redeem-points-{wallet.id}-{uuid4().hex[:12]}"
        )
        points_to_redeem = wallet.loyalty_points
        updated_wallet, entry, _ = wallet.redeem_loyalty_points(
            idempotency_key=norm_key,
            reference=f"Canje de {points_to_redeem} Puntos Cashback a Saldo COP",
        )
        saved_wallet, saved_entry = await self._repository.add_ledger_entry(
            updated_wallet,
            entry,
        )

        await self._event_bus.publish(
            WalletCreditedEvent(
                wallet_id=saved_wallet.id,
                user_id=saved_wallet.user_id,
                amount_cents=saved_entry.amount_cents,
                new_balance_cents=saved_wallet.balance_cents,
                currency=saved_wallet.currency,
                reference=saved_entry.reference,
                idempotency_key=saved_entry.idempotency_key,
            )
        )

        return (
            WalletDTO.from_entity(saved_wallet),
            LedgerEntryDTO.from_entity(saved_entry),
        )
