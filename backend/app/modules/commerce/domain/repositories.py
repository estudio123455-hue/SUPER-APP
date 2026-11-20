"""Abstract repository and payment port contracts for the Commerce domain (Law 3)."""

from typing import Protocol
from uuid import UUID

from app.modules.commerce.domain.entities import Order, Product, PromoCoupon


class ProductRepository(Protocol):
    """Port for persisting and querying catalog Products."""

    async def get_by_id(self, product_id: UUID) -> Product | None:
        """Finds a product by its unique UUID."""
        ...

    async def get_by_sku(self, sku: str) -> Product | None:
        """Finds a product by its normalized SKU."""
        ...

    async def list_active(self) -> list[Product]:
        """Lists all active products with available stock."""
        ...

    async def save(self, product: Product) -> Product:
        """Persists a new or updated Product entity."""
        ...


class OrderRepository(Protocol):
    """Port for persisting and querying buyer Orders."""

    async def get_by_id(self, order_id: UUID) -> Order | None:
        """Finds an order by its unique UUID."""
        ...

    async def get_by_idempotency_key(self, idempotency_key: str) -> Order | None:
        """Finds an order by its unique idempotency_key."""
        ...

    async def list_by_buyer(self, buyer_id: UUID) -> list[Order]:
        """Lists all orders placed by a specific buyer."""
        ...

    async def save(self, order: Order) -> Order:
        """Persists a new or updated Order entity along with its OrderItems."""
        ...


class PromoCouponRepository(Protocol):
    """Port for persisting and querying promotional coupons in commerce_schema."""

    async def get_by_code(self, code: str) -> PromoCoupon | None:
        """Finds a promo coupon by its normalized uppercase code."""
        ...

    async def list_all(self) -> list[PromoCoupon]:
        """Lists all promo coupons in the catalog."""
        ...

    async def save(self, coupon: PromoCoupon) -> PromoCoupon:
        """Persists a new or updated PromoCoupon entity."""
        ...


class WalletPaymentPort(Protocol):
    """Port for charging a buyer's wallet and querying VIP tier without coupling domain to wallet infrastructure."""

    async def charge(
        self,
        buyer_id: UUID,
        amount_cents: int,
        reference: str,
        idempotency_key: str,
    ) -> None:
        """Debits amount_cents from the buyer's wallet or raises OrderPaymentFailedError."""
        ...

    async def get_loyalty_tier(self, buyer_id: UUID) -> str:
        """Queries the buyer's VIP loyalty tier ('BRONZE', 'SILVER', 'GOLD')."""
        ...
