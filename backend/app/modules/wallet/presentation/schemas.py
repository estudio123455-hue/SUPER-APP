"""Pydantic v2 request and response schemas for the Wallet presentation layer."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.modules.wallet.domain.entities import TransactionStatus, TransactionType


class TransactionRequest(BaseModel):
    """Payload for depositing (CREDIT) or withdrawing (DEBIT) funds."""

    model_config = ConfigDict(from_attributes=True)

    amount_cents: int = Field(
        ...,
        gt=0,
        description="Amount in integer cents (strictly > 0).",
        examples=[50000_00],
    )
    reference: str = Field(
        ...,
        min_length=2,
        max_length=255,
        examples=["PSE Top-up #9812"],
    )
    idempotency_key: str = Field(
        ...,
        min_length=4,
        max_length=128,
        examples=["topup-user-123-req-001"],
    )


class LedgerEntryResponse(BaseModel):
    """Public representation of a single accounting ledger movement."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    wallet_id: UUID
    amount_cents: int
    transaction_type: TransactionType
    status: TransactionStatus
    reference: str
    idempotency_key: str
    created_at: datetime


class WalletSummaryResponse(BaseModel):
    """Public representation of a user's wallet state."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    user_id: UUID
    currency: str
    balance_cents: int
    loyalty_tier: str = "BRONZE"
    loyalty_points: int = 0
    lifetime_volume_cents: int = 0
    is_locked: bool
    created_at: datetime


class WalletMeResponse(BaseModel):
    """Response for GET /api/v1/wallet/me including recent ledger movements."""

    model_config = ConfigDict(from_attributes=True)

    wallet: WalletSummaryResponse
    recent_entries: list[LedgerEntryResponse]


class TransactionResultResponse(BaseModel):
    """Response returned after a successful deposit or withdrawal."""

    model_config = ConfigDict(from_attributes=True)

    wallet: WalletSummaryResponse
    entry: LedgerEntryResponse


class PaymentGatewayWebhookRequest(BaseModel):
    """External payment gateway webhook payload (PSE / Nequi / Wompi) verified via HMAC-SHA256."""

    model_config = ConfigDict(from_attributes=True)

    event_id: str = Field(
        ...,
        min_length=4,
        max_length=128,
        description="Unique gateway notification ID used as idempotency_key.",
        examples=["wompi-evt-2026-998811"],
    )
    user_id: UUID = Field(
        ...,
        description="Target user UUID whose wallet will be credited.",
    )
    amount_cents: int = Field(
        ...,
        gt=0,
        description="Approved payment amount in integer COP cents.",
        examples=[150000_00],
    )
    provider: str = Field(
        ...,
        min_length=2,
        max_length=32,
        examples=["NEQUI", "PSE", "WOMPI"],
    )


class PaymentGatewayWebhookResponse(BaseModel):
    """Response returned after processing an idempotent payment gateway webhook."""

    model_config = ConfigDict(from_attributes=True)

    wallet: WalletSummaryResponse
    entry: LedgerEntryResponse
    provider: str
    already_processed: bool = False
