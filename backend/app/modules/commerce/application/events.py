"""Domain events emitted by the Commerce bounded context."""

from dataclasses import dataclass
from uuid import UUID

from app.core.event_bus import DomainEvent


@dataclass(frozen=True, kw_only=True)
class ProductCreatedEvent(DomainEvent):
    """Published when a merchant creates a new catalog product."""

    product_id: UUID
    merchant_id: UUID
    sku: str
    title: str
    price_cents: int
    unit_cost_cents: int = 0
    stock_quantity: int


@dataclass(frozen=True, kw_only=True)
class ProductPriceAdjustedEvent(DomainEvent):
    """Published when the dynamic pricing engine adjusts a product's selling price."""

    product_id: UUID
    sku: str
    old_price_cents: int
    new_price_cents: int
    pricing_strategy: str
    margin_percentage: float


@dataclass(frozen=True, kw_only=True)
class OrderPlacedEvent(DomainEvent):
    """Published when an order is confirmed for Cash on Delivery dispatch."""

    order_id: UUID
    buyer_id: UUID
    total_cents: int
    currency: str
    payment_method: str
    idempotency_key: str
    source_job_id: UUID | None = None


@dataclass(frozen=True, kw_only=True)
class OrderPaidEvent(DomainEvent):
    """Published when an order is paid immediately via Wallet and confirmed."""

    order_id: UUID
    buyer_id: UUID
    total_cents: int
    currency: str
    payment_method: str
    idempotency_key: str
    source_job_id: UUID | None = None


@dataclass(frozen=True, kw_only=True)
class OrderShippedEvent(DomainEvent):
    """Published when a confirmed order is dispatched with carrier and tracking guide."""

    order_id: UUID
    buyer_id: UUID
    carrier_name: str
    tracking_code: str
    payment_method: str
    total_cents: int
    shipping_address: str


@dataclass(frozen=True, kw_only=True)
class OrderDeliveredAndSettledEvent(DomainEvent):
    """Published when an order is marked DELIVERED so Wallet can settle COD revenue."""

    order_id: UUID
    merchant_id: UUID
    buyer_id: UUID
    payment_method: str
    gross_total_cents: int
    total_cogs_cents: int
    shipping_cost_cents: int
    net_profit_cents: int
    source_job_id: UUID | None = None
