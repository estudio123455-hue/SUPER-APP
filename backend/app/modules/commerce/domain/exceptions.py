"""Pure domain exceptions for the Commerce bounded context (Law 3)."""


class CommerceDomainError(Exception):
    """Base domain exception for the Commerce module."""


class ProductNotFoundError(CommerceDomainError):
    """Raised when a product cannot be found by ID or SKU."""

    def __init__(self, identifier: str) -> None:
        super().__init__(f"Product '{identifier}' was not found.")
        self.identifier = identifier


class DuplicateSkuError(CommerceDomainError):
    """Raised when attempting to create a product with an existing SKU."""

    def __init__(self, sku: str) -> None:
        super().__init__(f"A product with SKU '{sku}' already exists.")
        self.sku = sku


class InsufficientStockError(CommerceDomainError):
    """Raised when requested quantity exceeds available product inventory."""

    def __init__(self, sku: str, available: int, requested: int) -> None:
        super().__init__(
            f"Insufficient stock for SKU '{sku}': available={available}, requested={requested}."
        )
        self.sku = sku
        self.available = available
        self.requested = requested


class OrderNotFoundError(CommerceDomainError):
    """Raised when an order cannot be found by ID."""

    def __init__(self, order_id: str) -> None:
        super().__init__(f"Order '{order_id}' was not found.")
        self.order_id = order_id


class OrderPaymentFailedError(CommerceDomainError):
    """Raised when charging the buyer's wallet fails during checkout."""

    def __init__(self, reason: str) -> None:
        super().__init__(f"Order payment failed: {reason}")
        self.reason = reason


class EmptyOrderError(CommerceDomainError):
    """Raised when attempting to place an order without any items."""

    def __init__(self) -> None:
        super().__init__("Cannot place an order with zero items.")


class InvalidOrderStateTransitionError(CommerceDomainError):
    """Raised when attempting an invalid state transition on an Order (e.g. delivering twice)."""

    def __init__(self, current_status: str, target_status: str) -> None:
        super().__init__(
            f"Cannot transition Order from '{current_status}' to '{target_status}'."
        )
        self.current_status = current_status
        self.target_status = target_status


class InvalidPromoCouponError(CommerceDomainError):
    """Raised when a promotional coupon code does not exist, is inactive, or exceeded max uses."""

    def __init__(
        self,
        code: str,
        reason: str = "Invalid or expired promotional coupon.",
    ) -> None:
        super().__init__(f"Coupon '{code}' cannot be applied: {reason}")
        self.code = code
        self.reason = reason
