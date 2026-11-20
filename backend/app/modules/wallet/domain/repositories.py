"""Abstract repository contracts for the Wallet domain (Law 3)."""

from typing import Protocol
from uuid import UUID

from app.modules.wallet.domain.entities import LedgerEntry, Wallet


class WalletRepository(Protocol):
    """Port for persisting Wallets and their LedgerEntries atomically."""

    async def get_by_user_id(self, user_id: UUID) -> Wallet | None:
        """Finds a user's wallet by user_id."""
        ...

    async def save(self, wallet: Wallet) -> Wallet:
        """Creates or updates a Wallet entity."""
        ...

    async def add_ledger_entry(
        self,
        wallet: Wallet,
        entry: LedgerEntry,
    ) -> tuple[Wallet, LedgerEntry]:
        """Atomically updates the wallet balance and records a new LedgerEntry."""
        ...

    async def get_ledger_by_key(self, idempotency_key: str) -> LedgerEntry | None:
        """Finds an existing LedgerEntry by its unique idempotency_key."""
        ...

    async def list_entries(
        self,
        wallet_id: UUID,
        limit: int = 20,
    ) -> list[LedgerEntry]:
        """Lists the most recent LedgerEntries for a given wallet."""
        ...
