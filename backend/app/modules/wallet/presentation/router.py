"""FastAPI router for the Wallet bounded context (/api/v1/wallet)."""

from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db_session
from app.core.event_bus import event_bus
from app.modules.identity.public_api import UserPublicDTO, get_current_user
from app.modules.wallet.application.dtos import (
    ProcessPaymentWebhookCommand,
    ProcessTransactionCommand,
)
from app.modules.wallet.application.use_cases import (
    GetWalletBalanceUseCase,
    ProcessPaymentGatewayWebhookUseCase,
    ProcessTransactionUseCase,
    RedeemLoyaltyPointsUseCase,
)
from app.modules.wallet.domain.entities import TransactionType
from app.modules.wallet.domain.exceptions import (
    DuplicateTransactionError,
    InsufficientFundsError,
    WalletLockedError,
    WalletNotFoundError,
)
from app.modules.wallet.infrastructure.repositories import SqlAlchemyWalletRepository
from app.modules.wallet.infrastructure.security import verify_payment_webhook_signature
from app.modules.wallet.presentation.schemas import (
    LedgerEntryResponse,
    PaymentGatewayWebhookRequest,
    PaymentGatewayWebhookResponse,
    TransactionRequest,
    TransactionResultResponse,
    WalletMeResponse,
    WalletSummaryResponse,
)

router = APIRouter(prefix="/api/v1/wallet", tags=["Wallet"])


@router.get(
    "/me",
    response_model=WalletMeResponse,
    status_code=status.HTTP_200_OK,
)
async def get_my_wallet(
    current_user: Annotated[UserPublicDTO, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> WalletMeResponse:
    """Returns the authenticated user's wallet balance and recent ledger movements."""
    repository = SqlAlchemyWalletRepository(session)
    use_case = GetWalletBalanceUseCase(repository=repository)

    try:
        balance_dto = await use_case.execute(user_id=current_user.id)
    except WalletNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc

    return WalletMeResponse(
        wallet=WalletSummaryResponse.model_validate(balance_dto.wallet),
        recent_entries=[
            LedgerEntryResponse.model_validate(e) for e in balance_dto.recent_entries
        ],
    )


@router.post(
    "/me/deposit",
    response_model=TransactionResultResponse,
    status_code=status.HTTP_201_CREATED,
)
async def deposit_funds(
    payload: TransactionRequest,
    current_user: Annotated[UserPublicDTO, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> TransactionResultResponse:
    """Credits funds into the authenticated user's wallet with idempotency protection."""
    repository = SqlAlchemyWalletRepository(session)
    use_case = ProcessTransactionUseCase(
        repository=repository,
        event_bus=event_bus,
    )

    try:
        wallet_dto, entry_dto = await use_case.execute(
            ProcessTransactionCommand(
                user_id=current_user.id,
                amount_cents=payload.amount_cents,
                transaction_type=TransactionType.CREDIT,
                reference=payload.reference,
                idempotency_key=payload.idempotency_key,
            )
        )
    except WalletNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except DuplicateTransactionError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc
    except WalletLockedError as exc:
        raise HTTPException(
            status_code=status.HTTP_423_LOCKED,
            detail=str(exc),
        ) from exc

    return TransactionResultResponse(
        wallet=WalletSummaryResponse.model_validate(wallet_dto),
        entry=LedgerEntryResponse.model_validate(entry_dto),
    )


@router.post(
    "/me/withdraw",
    response_model=TransactionResultResponse,
    status_code=status.HTTP_201_CREATED,
)
async def withdraw_funds(
    payload: TransactionRequest,
    current_user: Annotated[UserPublicDTO, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> TransactionResultResponse:
    """Debits funds from the authenticated user's wallet, validating available balance."""
    repository = SqlAlchemyWalletRepository(session)
    use_case = ProcessTransactionUseCase(
        repository=repository,
        event_bus=event_bus,
    )

    try:
        wallet_dto, entry_dto = await use_case.execute(
            ProcessTransactionCommand(
                user_id=current_user.id,
                amount_cents=payload.amount_cents,
                transaction_type=TransactionType.DEBIT,
                reference=payload.reference,
                idempotency_key=payload.idempotency_key,
            )
        )
    except WalletNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except DuplicateTransactionError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc
    except InsufficientFundsError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    except WalletLockedError as exc:
        raise HTTPException(
            status_code=status.HTTP_423_LOCKED,
            detail=str(exc),
        ) from exc

    return TransactionResultResponse(
        wallet=WalletSummaryResponse.model_validate(wallet_dto),
        entry=LedgerEntryResponse.model_validate(entry_dto),
    )


@router.post(
    "/me/redeem-points",
    response_model=TransactionResultResponse,
    status_code=status.HTTP_200_OK,
)
async def redeem_loyalty_points(
    current_user: Annotated[UserPublicDTO, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> TransactionResultResponse:
    """Converts the authenticated user's accumulated cashback points directly into liquid balance."""
    repository = SqlAlchemyWalletRepository(session)
    use_case = RedeemLoyaltyPointsUseCase(
        repository=repository,
        event_bus=event_bus,
    )

    try:
        wallet_dto, entry_dto = await use_case.execute(user_id=current_user.id)
    except WalletNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    except WalletLockedError as exc:
        raise HTTPException(
            status_code=status.HTTP_423_LOCKED,
            detail=str(exc),
        ) from exc

    return TransactionResultResponse(
        wallet=WalletSummaryResponse.model_validate(wallet_dto),
        entry=LedgerEntryResponse.model_validate(entry_dto),
    )


@router.post(
    "/webhooks/payment-gateway",
    response_model=PaymentGatewayWebhookResponse,
    status_code=status.HTTP_200_OK,
)
async def receive_payment_gateway_webhook(
    request: Request,
    payload: PaymentGatewayWebhookRequest,
    session: Annotated[AsyncSession, Depends(get_db_session)],
    x_webhook_signature: Annotated[
        str | None,
        Header(alias="X-Webhook-Signature"),
    ] = None,
) -> PaymentGatewayWebhookResponse:
    """Validates HMAC-SHA256 signature and idempotently credits user wallet from PSE/Nequi/Wompi."""
    raw_body = await request.body()
    canonical = (
        f"{payload.event_id}:{payload.user_id}:"
        f"{payload.amount_cents}:{payload.provider.strip().upper()}"
    )
    if not verify_payment_webhook_signature(
        raw_body=raw_body,
        provided_signature=x_webhook_signature,
        canonical_payload=canonical,
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing X-Webhook-Signature HMAC-SHA256 digest.",
        )

    repository = SqlAlchemyWalletRepository(session)
    use_case = ProcessPaymentGatewayWebhookUseCase(
        repository=repository,
        event_bus=event_bus,
    )

    try:
        result_dto = await use_case.execute(
            ProcessPaymentWebhookCommand(
                event_id=payload.event_id,
                user_id=payload.user_id,
                amount_cents=payload.amount_cents,
                provider=payload.provider,
            )
        )
    except WalletLockedError as exc:
        raise HTTPException(
            status_code=status.HTTP_423_LOCKED,
            detail=str(exc),
        ) from exc

    return PaymentGatewayWebhookResponse(
        wallet=WalletSummaryResponse.model_validate(result_dto.wallet),
        entry=LedgerEntryResponse.model_validate(result_dto.entry),
        provider=result_dto.provider,
        already_processed=result_dto.already_processed,
    )
