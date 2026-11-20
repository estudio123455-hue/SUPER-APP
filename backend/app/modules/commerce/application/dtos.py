"""Application commands and DTOs for the Commerce module."""

from dataclasses import dataclass
from datetime import datetime
from urllib.parse import quote
from uuid import UUID

from app.modules.commerce.domain.entities import (
    Order,
    OrderItem,
    OrderStatus,
    PaymentMethod,
    Product,
    ProductVariant,
    PromoCoupon,
    build_customer_lifecycle_messages,
)

DEFAULT_MERCHANT_WHATSAPP = "573000000000"


@dataclass(frozen=True, kw_only=True)
class ProductVariantDTO:
    """Application DTO representing a product SKU variant."""

    variant_sku: str
    size: str | None = None
    color: str | None = None
    stock_quantity: int = 0

    @classmethod
    def from_entity(cls, variant: ProductVariant) -> "ProductVariantDTO":
        return cls(
            variant_sku=variant.variant_sku,
            size=variant.size,
            color=variant.color,
            stock_quantity=variant.stock_quantity,
        )


@dataclass(frozen=True, kw_only=True)
class CreateProductCommand:
    """Command to create a new product in the catalog with unit COGS, variants, and category tags."""

    merchant_id: UUID
    sku: str
    title: str
    description: str
    price_cents: int
    unit_cost_cents: int = 0
    stock_quantity: int
    variants: tuple[ProductVariant, ...] = ()
    category_tag: str = "GENERAL"
    complement_tags: tuple[str, ...] = ()


@dataclass(frozen=True, kw_only=True)
class RestockProductCommand:
    """Command to add positive inventory units to an existing product."""

    product_id: UUID
    quantity_to_add: int


@dataclass(frozen=True, kw_only=True)
class ApplyDynamicPricingCommand:
    """Command to run the dynamic pricing engine on a catalog product."""

    product_id: UUID
    demand_conversions: int = 0


@dataclass(frozen=True, kw_only=True)
class OrderItemInputDTO:
    """Requested product and quantity inside a PlaceOrderCommand with optional variant selection."""

    product_id: UUID
    quantity: int
    variant_sku: str | None = None


@dataclass(frozen=True, kw_only=True)
class PlaceOrderCommand:
    """Command to place a new order using WALLET or CASH_ON_DELIVERY."""

    buyer_id: UUID
    items: tuple[OrderItemInputDTO, ...]
    payment_method: PaymentMethod
    shipping_address: str
    idempotency_key: str
    shipping_cost_cents: int = 0
    source_job_id: UUID | None = None
    coupon_code: str | None = None


@dataclass(frozen=True, kw_only=True)
class CreatePromoCouponCommand:
    """Command to create or update a promotional coupon with COGS floor protection."""

    code: str
    discount_percentage: int
    max_uses: int | None = None


@dataclass(frozen=True, kw_only=True)
class PromoCouponDTO:
    """Application DTO representing a PromoCoupon."""

    id: UUID
    code: str
    discount_percentage: int
    is_active: bool
    times_used: int
    max_uses: int | None
    created_at: datetime

    @classmethod
    def from_entity(cls, coupon: PromoCoupon) -> "PromoCouponDTO":
        return cls(
            id=coupon.id,
            code=coupon.code,
            discount_percentage=coupon.discount_percentage,
            is_active=coupon.is_active,
            times_used=coupon.times_used,
            max_uses=coupon.max_uses,
            created_at=coupon.created_at,
        )


@dataclass(frozen=True, kw_only=True)
class ShipOrderCommand:
    """Command to mark an order as SHIPPED with carrier and tracking guide."""

    order_id: UUID
    carrier_name: str
    tracking_code: str


@dataclass(frozen=True, kw_only=True)
class ProductDTO:
    """Application DTO representing a catalog Product with margin analytics, variants, and categories."""

    id: UUID
    merchant_id: UUID
    sku: str
    title: str
    description: str
    price_cents: int
    unit_cost_cents: int
    unit_margin_cents: int
    margin_percentage: float
    stock_quantity: int
    variants: tuple[ProductVariantDTO, ...] = ()
    category_tag: str = "GENERAL"
    complement_tags: tuple[str, ...] = ()
    is_active: bool = True
    created_at: datetime

    @classmethod
    def from_entity(cls, product: Product) -> "ProductDTO":
        return cls(
            id=product.id,
            merchant_id=product.merchant_id,
            sku=product.sku,
            title=product.title,
            description=product.description,
            price_cents=product.price_cents,
            unit_cost_cents=product.unit_cost_cents,
            unit_margin_cents=product.unit_margin_cents,
            margin_percentage=product.margin_percentage,
            stock_quantity=product.stock_quantity,
            variants=tuple(ProductVariantDTO.from_entity(v) for v in product.variants),
            category_tag=product.category_tag,
            complement_tags=product.complement_tags,
            is_active=product.is_active,
            created_at=product.created_at,
        )


@dataclass(frozen=True, kw_only=True)
class CrossSellBundleDTO:
    """Application DTO representing a smart AI cross-sell bundle recommendation."""

    anchor_product_id: UUID
    anchor_sku: str
    anchor_title: str
    anchor_price_cents: int
    complement_product_id: UUID
    complement_sku: str
    complement_title: str
    complement_price_cents: int
    bundle_name: str
    original_total_cents: int
    bundle_price_cents: int
    savings_cents: int
    discount_percentage: float
    combined_cogs_cents: int


@dataclass(frozen=True, kw_only=True)
class DynamicPriceResultDTO:
    """Application DTO returned after applying dynamic pricing to a product."""

    product: ProductDTO
    old_price_cents: int
    new_price_cents: int
    pricing_strategy: str


@dataclass(frozen=True, kw_only=True)
class OrderItemDTO:
    """Application DTO representing an Order line item."""

    product_id: UUID
    sku: str
    title: str
    unit_price_cents: int
    unit_cost_cents: int
    quantity: int
    subtotal_cents: int
    subtotal_cost_cents: int
    variant_sku: str | None = None

    @classmethod
    def from_entity(cls, item: OrderItem) -> "OrderItemDTO":
        return cls(
            product_id=item.product_id,
            sku=item.sku,
            title=item.title,
            unit_price_cents=item.unit_price_cents,
            unit_cost_cents=item.unit_cost_cents,
            quantity=item.quantity,
            subtotal_cents=item.subtotal_cents,
            subtotal_cost_cents=item.subtotal_cost_cents,
            variant_sku=item.variant_sku,
        )


def build_whatsapp_checkout_url(order: Order) -> str:
    """Builds a pre-filled WhatsApp Business wa.me link for order confirmation and dispatch."""
    items_summary = ", ".join(
        f"{item.quantity}x {item.title} (${item.subtotal_cents // 100:,} COP)"
        for item in order.items
    )
    total_cop = f"${order.total_cents // 100:,} {order.currency}"
    payment_label = (
        "PAGADO CON BILLETERA SUPER APP"
        if order.payment_method == PaymentMethod.WALLET
        else "PAGO CONTRAENTREGA (COD)"
    )
    attribution_line = (
        f"\n- Video Origen: #{str(order.source_job_id)[:8]}"
        if order.source_job_id is not None
        else ""
    )
    message = (
        f"Hola! Quiero confirmar mi pedido #{str(order.id)[:8]} en Super App.\n"
        f"- Productos: {items_summary}\n"
        f"- Total: {total_cop}\n"
        f"- Modalidad: {payment_label}\n"
        f"- Dirección de entrega: {order.shipping_address}"
        f"{attribution_line}"
    )
    return f"https://wa.me/{DEFAULT_MERCHANT_WHATSAPP}?text={quote(message)}"


@dataclass(frozen=True, kw_only=True)
class OrderDTO:
    """Application DTO representing a customer Order with full unit economics."""

    id: UUID
    buyer_id: UUID
    items: tuple[OrderItemDTO, ...]
    total_cents: int
    shipping_cost_cents: int
    total_cogs_cents: int
    net_profit_cents: int
    currency: str
    payment_method: PaymentMethod
    status: OrderStatus
    shipping_address: str
    idempotency_key: str
    source_job_id: UUID | None
    carrier_name: str | None = None
    tracking_code: str | None = None
    coupon_code: str | None = None
    discount_cents: int = 0
    whatsapp_checkout_url: str
    created_at: datetime

    @classmethod
    def from_entity(cls, order: Order) -> "OrderDTO":
        return cls(
            id=order.id,
            buyer_id=order.buyer_id,
            items=tuple(OrderItemDTO.from_entity(i) for i in order.items),
            total_cents=order.total_cents,
            shipping_cost_cents=order.shipping_cost_cents,
            total_cogs_cents=order.total_cogs_cents,
            net_profit_cents=order.net_profit_cents,
            currency=order.currency,
            payment_method=order.payment_method,
            status=order.status,
            shipping_address=order.shipping_address,
            idempotency_key=order.idempotency_key,
            source_job_id=order.source_job_id,
            carrier_name=order.carrier_name,
            tracking_code=order.tracking_code,
            coupon_code=order.coupon_code,
            discount_cents=order.discount_cents,
            whatsapp_checkout_url=build_whatsapp_checkout_url(order),
            created_at=order.created_at,
        )


@dataclass(frozen=True, kw_only=True)
class OrderLifecycleMessagesDTO:
    """Application DTO containing the 3 automated post-sale customer messages and wa.me URLs."""

    order_id: UUID
    status: OrderStatus
    carrier_name: str | None
    tracking_code: str | None
    confirmation_msg: str
    shipping_msg: str
    post_delivery_msg: str
    confirmation_whatsapp_url: str
    shipping_whatsapp_url: str
    post_delivery_whatsapp_url: str

    @classmethod
    def from_entity(cls, order: Order) -> "OrderLifecycleMessagesDTO":
        messages = build_customer_lifecycle_messages(order)
        conf_msg = messages["confirmation_msg"]
        ship_msg = messages["shipping_msg"]
        post_msg = messages["post_delivery_msg"]
        return cls(
            order_id=order.id,
            status=order.status,
            carrier_name=order.carrier_name,
            tracking_code=order.tracking_code,
            confirmation_msg=conf_msg,
            shipping_msg=ship_msg,
            post_delivery_msg=post_msg,
            confirmation_whatsapp_url=f"https://wa.me/{DEFAULT_MERCHANT_WHATSAPP}?text={quote(conf_msg)}",
            shipping_whatsapp_url=f"https://wa.me/{DEFAULT_MERCHANT_WHATSAPP}?text={quote(ship_msg)}",
            post_delivery_whatsapp_url=f"https://wa.me/{DEFAULT_MERCHANT_WHATSAPP}?text={quote(post_msg)}",
        )


@dataclass(frozen=True, kw_only=True)
class CommerceFinancialSummaryDTO:
    """Real-time unit economics summary across inventory and orders."""

    inventory_cost_value_cents: int
    inventory_retail_value_cents: int
    potential_inventory_profit_cents: int
    orders_count: int
    delivered_orders_count: int
    gross_revenue_cents: int
    accumulated_cogs_cents: int
    accumulated_shipping_cents: int
    realized_net_profit_cents: int
