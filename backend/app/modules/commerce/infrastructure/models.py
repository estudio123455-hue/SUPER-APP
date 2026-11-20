"""SQLAlchemy 2.0 models for the Commerce module isolated in 'commerce_schema' (Law 2).

No ForeignKeys to identity_schema, wallet_schema, or media_ai_schema are permitted;
merchant_id, buyer_id, and source_job_id are stored as pure indexed UUIDs.
"""

from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy import JSON, BigInteger, Boolean, DateTime, Integer, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import build_schema_base

CommerceBase = build_schema_base("commerce")


class ProductModel(CommerceBase):
    """Database representation of a catalog Product in commerce_schema."""

    __tablename__ = "products"

    id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )
    merchant_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        index=True,
        nullable=False,
    )
    sku: Mapped[str] = mapped_column(
        String(64),
        unique=True,
        index=True,
        nullable=False,
    )
    title: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    description: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        default="",
    )
    price_cents: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"),
        nullable=False,
    )
    unit_cost_cents: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"),
        nullable=False,
        default=0,
    )
    stock_quantity: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )
    variants: Mapped[list[dict] | None] = mapped_column(
        JSON,
        nullable=True,
        default=list,
    )
    category_tag: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        default="GENERAL",
    )
    complement_tags: Mapped[list[str] | None] = mapped_column(
        JSON,
        nullable=True,
        default=list,
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
    )


class OrderModel(CommerceBase):
    """Database representation of a buyer Order in commerce_schema."""

    __tablename__ = "orders"

    id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )
    buyer_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        index=True,
        nullable=False,
    )
    total_cents: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"),
        nullable=False,
    )
    shipping_cost_cents: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"),
        nullable=False,
        default=0,
    )
    currency: Mapped[str] = mapped_column(
        String(3),
        nullable=False,
        default="COP",
    )
    payment_method: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
    )
    status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
    )
    shipping_address: Mapped[str] = mapped_column(
        String(512),
        nullable=False,
    )
    idempotency_key: Mapped[str] = mapped_column(
        String(128),
        unique=True,
        index=True,
        nullable=False,
    )
    source_job_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        index=True,
        nullable=True,
    )
    carrier_name: Mapped[str | None] = mapped_column(
        String(128),
        nullable=True,
    )
    tracking_code: Mapped[str | None] = mapped_column(
        String(128),
        nullable=True,
    )
    coupon_code: Mapped[str | None] = mapped_column(
        String(64),
        nullable=True,
    )
    discount_cents: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"),
        nullable=False,
        default=0,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
    )


class OrderItemModel(CommerceBase):
    """Database representation of an Order line item in commerce_schema."""

    __tablename__ = "order_items"

    id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )
    order_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        index=True,
        nullable=False,
    )
    product_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        index=True,
        nullable=False,
    )
    sku: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
    )
    title: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    unit_price_cents: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"),
        nullable=False,
    )
    unit_cost_cents: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"),
        nullable=False,
        default=0,
    )
    quantity: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )
    variant_sku: Mapped[str | None] = mapped_column(
        String(64),
        nullable=True,
        default=None,
    )


class PromoCouponModel(CommerceBase):
    """Database representation of a promotional coupon in commerce_schema."""

    __tablename__ = "promo_coupons"

    id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )
    code: Mapped[str] = mapped_column(
        String(64),
        unique=True,
        index=True,
        nullable=False,
    )
    discount_percentage: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
    )
    times_used: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )
    max_uses: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
    )
