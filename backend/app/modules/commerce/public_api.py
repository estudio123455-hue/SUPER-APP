"""Public API contract for the commerce module (Law 1).

Other bounded contexts (e.g. media_ai, wallet) MUST ONLY import from this file
when querying catalog products or subscribing to commerce events.
"""

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.commerce.application.events import (
    OrderDeliveredAndSettledEvent,
    OrderPaidEvent,
    OrderPlacedEvent,
    OrderShippedEvent,
    ProductCreatedEvent,
)
from app.modules.commerce.domain.entities import build_smart_bundle_recommendation
from app.modules.commerce.domain.exceptions import ProductNotFoundError
from app.modules.commerce.infrastructure.repositories import SqlAlchemyProductRepository


@dataclass(frozen=True, kw_only=True)
class ProductPublicDTO:
    """Immutable cross-module representation of a catalog Product."""

    id: UUID
    merchant_id: UUID
    sku: str
    title: str
    description: str
    price_cents: int
    unit_cost_cents: int
    stock_quantity: int
    is_active: bool
    created_at: datetime


@dataclass(frozen=True, kw_only=True)
class OrderPublicDTO:
    """Immutable cross-module summary of a customer Order."""

    id: UUID
    buyer_id: UUID
    total_cents: int
    currency: str
    payment_method: str
    status: str
    created_at: datetime


async def get_product_public_info(
    product_id: UUID,
    session: AsyncSession,
) -> ProductPublicDTO:
    """Public contract for other modules (e.g. media_ai) to inspect product metadata."""
    repository = SqlAlchemyProductRepository(session)
    product = await repository.get_by_id(product_id)
    if product is None:
        raise ProductNotFoundError(str(product_id))

    return ProductPublicDTO(
        id=product.id,
        merchant_id=product.merchant_id,
        sku=product.sku,
        title=product.title,
        description=product.description,
        price_cents=product.price_cents,
        unit_cost_cents=product.unit_cost_cents,
        stock_quantity=product.stock_quantity,
        is_active=product.is_active,
        created_at=product.created_at,
    )


async def get_cross_sell_recommendation_public(
    product_id: UUID,
    session: AsyncSession,
) -> dict | None:
    """Public contract for media_ai or other bounded contexts to obtain cross-sell bundle recommendations."""
    repository = SqlAlchemyProductRepository(session)
    anchor = await repository.get_by_id(product_id)
    if anchor is None or not anchor.is_active:
        return None
    catalog = await repository.list_active()
    return build_smart_bundle_recommendation(
        anchor_product=anchor,
        catalog=catalog,
        bundle_discount_pct=12,
    )


__all__ = [
    "OrderDeliveredAndSettledEvent",
    "OrderPaidEvent",
    "OrderPlacedEvent",
    "OrderPublicDTO",
    "OrderShippedEvent",
    "ProductCreatedEvent",
    "ProductNotFoundError",
    "ProductPublicDTO",
    "get_cross_sell_recommendation_public",
    "get_product_public_info",
]
