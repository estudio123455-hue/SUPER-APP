"""Event handlers for the Wallet bounded context subscribing via EventBus (Law 1)."""

from app.core.database import get_session_factory
from app.core.event_bus import InMemoryEventBus, event_bus
from app.modules.commerce.public_api import OrderDeliveredAndSettledEvent
from app.modules.identity.public_api import UserRegisteredEvent
from app.modules.wallet.application.dtos import (
    CreateWalletCommand,
    ProcessTransactionCommand,
)
from app.modules.wallet.application.use_cases import (
    CreateWalletUseCase,
    CreditCashbackUseCase,
    ProcessTransactionUseCase,
)
from app.modules.wallet.domain.entities import TransactionType
from app.modules.wallet.domain.exceptions import DuplicateTransactionError
from app.modules.wallet.infrastructure.repositories import SqlAlchemyWalletRepository


async def on_user_registered(event: UserRegisteredEvent) -> None:
    """Automatically provisions a default COP wallet with 0 balance when a user registers."""
    session_factory = get_session_factory()
    async with session_factory() as session:
        repository = SqlAlchemyWalletRepository(session)
        use_case = CreateWalletUseCase(repository=repository)
        await use_case.execute(
            CreateWalletCommand(
                user_id=event.user_id,
                currency="COP",
            )
        )


async def on_order_delivered_and_settled(event: OrderDeliveredAndSettledEvent) -> None:
    """Settles delivered orders into merchant's Wallet and credits 3% cashback to buyer."""
    session_factory = get_session_factory()
    async with session_factory() as session:
        repository = SqlAlchemyWalletRepository(session)

        # 1. Settle COD net profit to merchant if applicable
        if event.payment_method == "CASH_ON_DELIVERY":
            settlement_cents = (
                event.net_profit_cents
                if event.net_profit_cents > 0
                else event.gross_total_cents
            )
            if settlement_cents > 0:
                await CreateWalletUseCase(repository=repository).execute(
                    CreateWalletCommand(user_id=event.merchant_id, currency="COP")
                )
                process_uc = ProcessTransactionUseCase(
                    repository=repository,
                    event_bus=event_bus,
                )
                try:
                    await process_uc.execute(
                        ProcessTransactionCommand(
                            user_id=event.merchant_id,
                            amount_cents=settlement_cents,
                            transaction_type=TransactionType.CREDIT,
                            reference=f"Liquidación Pedido Contraentrega #{str(event.order_id)[:8]}",
                            idempotency_key=f"settlement-{event.order_id}",
                        )
                    )
                except DuplicateTransactionError:
                    pass

        # 2. Credit 3% cashback and upgrade VIP tier to the buyer with idempotency cashback-{order_id}
        if event.gross_total_cents > 0:
            cashback_uc = CreditCashbackUseCase(
                repository=repository,
                event_bus=event_bus,
            )
            try:
                await cashback_uc.execute(
                    buyer_id=event.buyer_id,
                    order_id=event.order_id,
                    gross_total_cents=event.gross_total_cents,
                    cashback_rate=0.03,
                )
            except DuplicateTransactionError:
                pass


def register_wallet_event_handlers(bus: InMemoryEventBus) -> None:
    """Subscribes Wallet event handlers to the shared EventBus."""
    bus.subscribe(UserRegisteredEvent, on_user_registered)
    bus.subscribe(OrderDeliveredAndSettledEvent, on_order_delivered_and_settled)
