"""Pydantic v2 request and response schemas for the Commerce presentation layer."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.modules.commerce.domain.entities import OrderStatus, PaymentMethod


class CreateProductRequest(BaseModel):
    """Payload for creating a new catalog product with COGS unit economics."""

    model_config = ConfigDict(from_attributes=True)

    sku: str = Field(..., min_length=2, max_length=64, examples=["ERGO-STAND-PRO"])
    title: str = Field(
        ...,
        min_length=2,
        max_length=255,
        examples=["Soporte Ergonómico Pro Aluminio"],
    )
    description: str = Field(default="", max_length=2000)
    price_cents: int = Field(
        ...,
        gt=0,
        description="Selling unit price in integer COP cents.",
        examples=[95000_00],
    )
    unit_cost_cents: int = Field(
        default=0,
        ge=0,
        description="Unit acquisition/manufacturing cost (COGS) in integer COP cents.",
        examples=[42000_00],
    )
    stock_quantity: int = Field(..., ge=0, examples=[15])
    category_tag: str = Field(default="GENERAL", max_length=64, examples=["MENSWEAR"])
    complement_tags: list[str] = Field(default_factory=list, examples=[["MENSWEAR", "ACCESSORIES"]])


class RestockProductRequest(BaseModel):
    """Payload for adding inventory stock to an existing product."""

    model_config = ConfigDict(from_attributes=True)

    quantity_to_add: int = Field(
        ...,
        gt=0,
        description="Number of positive units to add to product stock.",
        examples=[5],
    )


class DynamicPricingRequest(BaseModel):
    """Payload for triggering dynamic price adjustment on a product."""

    model_config = ConfigDict(from_attributes=True)

    demand_conversions: int = Field(
        default=0,
        ge=0,
        description="Attributed sales conversions driving demand surge.",
    )


class ProductVariantResponse(BaseModel):
    """Public representation of a product SKU variant."""

    model_config = ConfigDict(from_attributes=True)

    variant_sku: str
    size: str | None = None
    color: str | None = None
    stock_quantity: int = 0


class ProductResponse(BaseModel):
    """Public representation of a catalog Product including margin analytics and variants."""

    model_config = ConfigDict(from_attributes=True)

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
    variants: list[ProductVariantResponse] = Field(default_factory=list)
    category_tag: str = "GENERAL"
    complement_tags: list[str] = Field(default_factory=list)
    is_active: bool
    created_at: datetime


class CrossSellBundleResponse(BaseModel):
    """Public representation of an AI smart cross-sell bundle recommendation."""

    model_config = ConfigDict(from_attributes=True)

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


class DynamicPricingResponse(BaseModel):
    """Response returned after applying dynamic pricing to a product."""

    model_config = ConfigDict(from_attributes=True)

    product: ProductResponse
    old_price_cents: int
    new_price_cents: int
    pricing_strategy: str


class OrderItemRequest(BaseModel):
    """Requested line item inside a PlaceOrderRequest."""

    model_config = ConfigDict(from_attributes=True)

    product_id: UUID
    quantity: int = Field(..., gt=0, examples=[1])
    variant_sku: str | None = Field(
        default=None,
        description="Optional SKU of the chosen variant (e.g. RBR-JKT-M-BLK)",
        examples=["RBR-JKT-M-BLK"],
    )


class PlaceOrderRequest(BaseModel):
    """Payload for placing an order via WALLET or CASH_ON_DELIVERY."""

    model_config = ConfigDict(from_attributes=True)

    items: list[OrderItemRequest] = Field(..., min_length=1)
    payment_method: PaymentMethod
    shipping_address: str = Field(
        ...,
        min_length=5,
        max_length=512,
        examples=["Calle 93 #11-27, Bogotá, Colombia"],
    )
    idempotency_key: str = Field(
        ...,
        min_length=4,
        max_length=128,
        examples=["order-checkout-2026-0001"],
    )
    shipping_cost_cents: int = Field(
        default=0,
        ge=0,
        description="Shipping carrier fee in integer COP cents.",
        examples=[12000_00],
    )
    source_job_id: UUID | None = Field(
        default=None,
        description="Optional Media AI Job UUID that originated this purchase.",
    )
    coupon_code: str | None = Field(
        default=None,
        max_length=64,
        description="Optional promotional coupon code (e.g. SUPER10) with COGS floor protection.",
        examples=["SUPER10"],
    )


class CreatePromoCouponRequest(BaseModel):
    """Payload for creating or updating a promotional coupon in commerce_schema."""

    model_config = ConfigDict(from_attributes=True)

    code: str = Field(
        ...,
        min_length=2,
        max_length=64,
        examples=["SUPER10"],
    )
    discount_percentage: int = Field(
        ...,
        ge=1,
        le=50,
        description="Discount percentage between 1% and 50% (protected by 1.15x COGS floor).",
        examples=[10],
    )
    max_uses: int | None = Field(
        default=None,
        gt=0,
        description="Optional maximum redemption cap.",
    )


class PromoCouponResponse(BaseModel):
    """Public representation of a promotional coupon."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    code: str
    discount_percentage: int
    is_active: bool
    times_used: int
    max_uses: int | None = None
    created_at: datetime


class OrderItemResponse(BaseModel):
    """Public representation of an Order line item."""

    model_config = ConfigDict(from_attributes=True)

    product_id: UUID
    sku: str
    title: str
    unit_price_cents: int
    unit_cost_cents: int
    quantity: int
    subtotal_cents: int
    subtotal_cost_cents: int
    variant_sku: str | None = None


class OrderResponse(BaseModel):
    """Public representation of a customer Order including unit economics & WhatsApp link."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    buyer_id: UUID
    items: list[OrderItemResponse]
    total_cents: int
    shipping_cost_cents: int
    total_cogs_cents: int
    net_profit_cents: int
    currency: str
    payment_method: PaymentMethod
    status: OrderStatus
    shipping_address: str
    idempotency_key: str
    source_job_id: UUID | None = None
    carrier_name: str | None = None
    tracking_code: str | None = None
    coupon_code: str | None = None
    discount_cents: int = 0
    whatsapp_checkout_url: str
    created_at: datetime


class ShipOrderRequest(BaseModel):
    """Payload for dispatching a confirmed order with carrier and tracking guide."""

    model_config = ConfigDict(from_attributes=True)

    carrier_name: str = Field(
        ...,
        min_length=2,
        max_length=128,
        examples=["InterRapidísimo"],
    )
    tracking_code: str = Field(
        ...,
        min_length=3,
        max_length=128,
        examples=["GUIA-2400991188"],
    )


class OrderLifecycleMessagesResponse(BaseModel):
    """Automated post-sale messages (Confirmation, Shipping, Post-Delivery) and direct wa.me links."""

    model_config = ConfigDict(from_attributes=True)

    order_id: UUID
    status: OrderStatus
    carrier_name: str | None = None
    tracking_code: str | None = None
    confirmation_msg: str
    shipping_msg: str
    post_delivery_msg: str
    confirmation_whatsapp_url: str
    shipping_whatsapp_url: str
    post_delivery_whatsapp_url: str


class CommerceFinancialSummaryResponse(BaseModel):
    """Real-time unit economics summary for the merchant dashboard."""

    model_config = ConfigDict(from_attributes=True)

    inventory_cost_value_cents: int
    inventory_retail_value_cents: int
    potential_inventory_profit_cents: int
    orders_count: int
    delivered_orders_count: int
    gross_revenue_cents: int
    accumulated_cogs_cents: int
    accumulated_shipping_cents: int
    realized_net_profit_cents: int
