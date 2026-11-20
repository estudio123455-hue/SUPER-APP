"""Pure domain entities and value objects for the Wallet bounded context (Law 3)."""

from dataclasses import dataclass, field, replace
from datetime import UTC, datetime
from enum import StrEnum
from uuid import UUID, uuid4

from app.modules.wallet.domain.exceptions import (
    InsufficientFundsError,
    WalletLockedError,
)


class TransactionType(StrEnum):
    """Types of financial ledger movements."""

    CREDIT = "CREDIT"
    DEBIT = "DEBIT"


class TransactionStatus(StrEnum):
    """Lifecycle status of a wallet transaction."""

    PENDING = "PENDING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class LoyaltyTier(StrEnum):
    """VIP Loyalty tier determined by cumulative delivered order volume."""

    BRONZE = "BRONZE"
    SILVER = "SILVER"
    GOLD = "GOLD"


@dataclass(frozen=True, kw_only=True)
class LedgerEntry:
    """Immutable accounting ledger movement associated with a Wallet."""

    id: UUID = field(default_factory=uuid4)
    wallet_id: UUID
    amount_cents: int
    transaction_type: TransactionType
    status: TransactionStatus = TransactionStatus.COMPLETED
    reference: str
    idempotency_key: str
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def __post_init__(self) -> None:
        if self.amount_cents <= 0:
            raise ValueError("LedgerEntry amount_cents must be strictly positive (> 0).")
        if not self.reference.strip():
            raise ValueError("LedgerEntry reference cannot be empty.")
        if not self.idempotency_key.strip():
            raise ValueError("LedgerEntry idempotency_key cannot be empty.")


@dataclass(frozen=True, kw_only=True)
class Wallet:
    """Pure domain entity representing a user's financial wallet."""

    id: UUID = field(default_factory=uuid4)
    user_id: UUID
    currency: str = "COP"
    balance_cents: int = 0
    loyalty_tier: LoyaltyTier = LoyaltyTier.BRONZE
    loyalty_points: int = 0
    lifetime_volume_cents: int = 0
    is_locked: bool = False
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def __post_init__(self) -> None:
        normalized_currency = self.currency.strip().upper()
        if len(normalized_currency) != 3:
            raise ValueError("Currency must be a 3-letter ISO code (e.g., 'COP').")
        object.__setattr__(self, "currency", normalized_currency)
        if self.balance_cents < 0:
            raise ValueError("Wallet balance_cents cannot be negative.")
        if self.loyalty_points < 0:
            raise ValueError("Wallet loyalty_points cannot be negative.")
        if self.lifetime_volume_cents < 0:
            raise ValueError("Wallet lifetime_volume_cents cannot be negative.")

    def _ensure_unlocked(self) -> None:
        if self.is_locked:
            raise WalletLockedError(str(self.id))

    def credit_cashback_and_upgrade_tier(
        self,
        order_gross_cents: int,
        cashback_rate: float = 0.03,
    ) -> "Wallet":
        """Calculates 3% cashback points from delivered order, accumulates lifetime volume and recalculates VIP tier."""
        self._ensure_unlocked()
        if order_gross_cents <= 0:
            return self

        cashback_points = int(order_gross_cents * cashback_rate)
        new_volume = self.lifetime_volume_cents + order_gross_cents
        new_points = self.loyalty_points + cashback_points

        # VIP Tier upgrade thresholds:
        # SILVER: >= $300,000 COP (30,000,000 cents)
        # GOLD: >= $1,000,000 COP (100,000,000 cents)
        if new_volume >= 100_000_000:
            tier = LoyaltyTier.GOLD
        elif new_volume >= 30_000_000:
            tier = LoyaltyTier.SILVER
        else:
            tier = LoyaltyTier.BRONZE

        return replace(
            self,
            loyalty_tier=tier,
            loyalty_points=new_points,
            lifetime_volume_cents=new_volume,
        )

    def redeem_loyalty_points(
        self,
        idempotency_key: str,
        reference: str = "Canje de Puntos Cashback a Saldo COP",
    ) -> tuple["Wallet", LedgerEntry, int]:
        """Converts all accumulated loyalty points directly into liquid balance_cents in COP."""
        self._ensure_unlocked()
        if self.loyalty_points <= 0:
            raise ValueError("No loyalty points available to redeem.")

        points_to_redeem = self.loyalty_points
        entry = LedgerEntry(
            wallet_id=self.id,
            amount_cents=points_to_redeem,
            transaction_type=TransactionType.CREDIT,
            status=TransactionStatus.COMPLETED,
            reference=reference.strip(),
            idempotency_key=idempotency_key.strip(),
        )
        updated_wallet = replace(
            self,
            balance_cents=self.balance_cents + points_to_redeem,
            loyalty_points=0,
        )
        return updated_wallet, entry, points_to_redeem

    def credit(
        self,
        amount_cents: int,
        reference: str,
        idempotency_key: str,
    ) -> tuple["Wallet", LedgerEntry]:
        """Credits positive cents to the wallet and returns the updated Wallet + LedgerEntry."""
        self._ensure_unlocked()
        if amount_cents <= 0:
            raise ValueError("Credit amount_cents must be strictly positive (> 0).")

        entry = LedgerEntry(
            wallet_id=self.id,
            amount_cents=amount_cents,
            transaction_type=TransactionType.CREDIT,
            status=TransactionStatus.COMPLETED,
            reference=reference.strip(),
            idempotency_key=idempotency_key.strip(),
        )
        updated_wallet = replace(self, balance_cents=self.balance_cents + amount_cents)
        return updated_wallet, entry

    def debit(
        self,
        amount_cents: int,
        reference: str,
        idempotency_key: str,
    ) -> tuple["Wallet", LedgerEntry]:
        """Debits positive cents from the wallet, preventing negative balances."""
        self._ensure_unlocked()
        if amount_cents <= 0:
            raise ValueError("Debit amount_cents must be strictly positive (> 0).")
        if self.balance_cents < amount_cents:
            raise InsufficientFundsError(
                available_cents=self.balance_cents,
                requested_cents=amount_cents,
            )

        entry = LedgerEntry(
            wallet_id=self.id,
            amount_cents=amount_cents,
            transaction_type=TransactionType.DEBIT,
            status=TransactionStatus.COMPLETED,
            reference=reference.strip(),
            idempotency_key=idempotency_key.strip(),
        )
        updated_wallet = replace(self, balance_cents=self.balance_cents - amount_cents)
        return updated_wallet, entry
