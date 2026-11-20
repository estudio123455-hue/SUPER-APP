"""Pure domain exceptions for the Wallet bounded context (Law 3)."""


class WalletDomainError(Exception):
    """Base domain exception for the Wallet module."""


class WalletNotFoundError(WalletDomainError):
    """Raised when a wallet cannot be found for a given user or wallet ID."""

    def __init__(self, identifier: str) -> None:
        super().__init__(f"Wallet for '{identifier}' was not found.")
        self.identifier = identifier


class InsufficientFundsError(WalletDomainError):
    """Raised when a debit exceeds the available wallet balance."""

    def __init__(self, available_cents: int, requested_cents: int) -> None:
        super().__init__(
            f"Insufficient funds: available={available_cents} cents, "
            f"requested={requested_cents} cents."
        )
        self.available_cents = available_cents
        self.requested_cents = requested_cents


class WalletLockedError(WalletDomainError):
    """Raised when attempting to transact on a locked/frozen wallet."""

    def __init__(self, wallet_id: str) -> None:
        super().__init__(f"Wallet '{wallet_id}' is currently locked.")
        self.wallet_id = wallet_id


class DuplicateTransactionError(WalletDomainError):
    """Raised when a ledger operation reuses an existing idempotency_key."""

    def __init__(self, idempotency_key: str) -> None:
        super().__init__(
            f"Transaction with idempotency_key '{idempotency_key}' has already been processed."
        )
        self.idempotency_key = idempotency_key
