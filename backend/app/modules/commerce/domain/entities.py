"""Pure domain entities and value objects for the Commerce bounded context (Law 3)."""

from dataclasses import dataclass, field, replace
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any
from uuid import UUID, uuid4

from app.modules.commerce.domain.exceptions import (
    EmptyOrderError,
    InsufficientStockError,
    InvalidOrderStateTransitionError,
    InvalidPromoCouponError,
)


class PaymentMethod(StrEnum):
    """Supported checkout payment methods."""

    WALLET = "WALLET"
    CASH_ON_DELIVERY = "CASH_ON_DELIVERY"


class OrderStatus(StrEnum):
    """Lifecycle states of a commerce order."""

    PENDING_PAYMENT = "PENDING_PAYMENT"
    CONFIRMED = "CONFIRMED"
    SHIPPED = "SHIPPED"
    DELIVERED = "DELIVERED"
    CANCELLED = "CANCELLED"


@dataclass(frozen=True, kw_only=True)
class ProductVariant:
    """Immutable value object representing a product SKU variant (size, color, stock)."""

    variant_sku: str
    size: str | None = None
    color: str | None = None
    stock_quantity: int = 0

    def __post_init__(self) -> None:
        normalized_sku = self.variant_sku.strip().upper()
        if not normalized_sku:
            raise ValueError("ProductVariant variant_sku cannot be empty.")
        object.__setattr__(self, "variant_sku", normalized_sku)
        if self.stock_quantity < 0:
            raise ValueError("ProductVariant stock_quantity cannot be negative.")

    def reserve_stock(self, quantity: int) -> "ProductVariant":
        """Deducts variant stock units, validating availability."""
        if quantity <= 0:
            raise ValueError("Quantity to reserve must be strictly positive (> 0).")
        if self.stock_quantity < quantity:
            raise InsufficientStockError(
                sku=self.variant_sku,
                available=self.stock_quantity,
                requested=quantity,
            )
        return replace(self, stock_quantity=self.stock_quantity - quantity)

    def release_stock(self, quantity: int) -> "ProductVariant":
        """Restores variant stock units."""
        if quantity <= 0:
            raise ValueError("Quantity to release must be strictly positive (> 0).")
        return replace(self, stock_quantity=self.stock_quantity + quantity)


@dataclass(frozen=True, kw_only=True)
class Product:
    """Immutable domain entity representing a catalog product with COGS, variants, category tags, and dynamic pricing."""

    id: UUID = field(default_factory=uuid4)
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
    is_active: bool = True
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def __post_init__(self) -> None:
        normalized_sku = self.sku.strip().upper()
        if not normalized_sku:
            raise ValueError("Product SKU cannot be empty.")
        object.__setattr__(self, "sku", normalized_sku)

        if not isinstance(self.variants, tuple):
            object.__setattr__(self, "variants", tuple(self.variants))

        cleaned_cat = self.category_tag.strip().upper() if self.category_tag else "GENERAL"
        object.__setattr__(self, "category_tag", cleaned_cat)

        if not isinstance(self.complement_tags, tuple):
            cleaned_complements = tuple(t.strip().upper() for t in self.complement_tags if t.strip())
            object.__setattr__(self, "complement_tags", cleaned_complements)
        else:
            cleaned_complements = tuple(t.strip().upper() for t in self.complement_tags if t.strip())
            object.__setattr__(self, "complement_tags", cleaned_complements)

        if not self.title.strip():
            raise ValueError("Product title cannot be empty.")
        if self.price_cents <= 0:
            raise ValueError("Product price_cents must be strictly positive (> 0).")
        if self.unit_cost_cents < 0:
            raise ValueError("Product unit_cost_cents cannot be negative.")
        if self.stock_quantity < 0:
            raise ValueError("Product stock_quantity cannot be negative.")

    @property
    def unit_margin_cents(self) -> int:
        """Gross margin per unit in integer cents (price_cents - unit_cost_cents)."""
        return self.price_cents - self.unit_cost_cents

    @property
    def margin_percentage(self) -> float:
        """Gross margin percentage relative to selling price."""
        return round((self.unit_margin_cents / self.price_cents) * 100.0, 2)

    @property
    def minimum_protected_price_cents(self) -> int:
        """Golden Rule floor: price can never drop below unit_cost_cents * 1.25."""
        if self.unit_cost_cents <= 0:
            return 1
        return (self.unit_cost_cents * 125 + 99) // 100

    def apply_dynamic_pricing(
        self,
        demand_conversions: int = 0,
    ) -> tuple["Product", str]:
        """Adjusts price_cents based on stock scarcity and demand while protecting minimum margin."""
        if demand_conversions < 0:
            raise ValueError("demand_conversions cannot be negative.")

        floor_cents = self.minimum_protected_price_cents

        if self.stock_quantity <= 3 or demand_conversions >= 3:
            surged = int(round(self.price_cents * 1.10))
            new_price = max(floor_cents, surged)
            return replace(self, price_cents=new_price), "SURGE_HIGH_DEMAND"

        if self.stock_quantity >= 15 and demand_conversions == 0:
            discounted = int(round(self.price_cents * 0.92))
            new_price = max(floor_cents, discounted)
            return replace(self, price_cents=new_price), "FLASH_ROTATION_DISCOUNT"

        new_price = max(floor_cents, self.price_cents)
        return replace(self, price_cents=new_price), "OPTIMAL_HOLD"

    def reserve_stock(
        self,
        quantity: int,
        variant_sku: str | None = None,
    ) -> "Product":
        """Deducts stock for an order, validating positive quantity, global stock, and variant isolation."""
        if quantity <= 0:
            raise ValueError("Quantity to reserve must be strictly positive (> 0).")

        if self.stock_quantity < quantity:
            raise InsufficientStockError(
                sku=self.sku,
                available=self.stock_quantity,
                requested=quantity,
            )

        new_variants = self.variants
        if self.variants:
            if variant_sku is not None and variant_sku.strip():
                normalized_vsku = variant_sku.strip().upper()
                found = False
                updated_list: list[ProductVariant] = []
                for v in self.variants:
                    if v.variant_sku == normalized_vsku:
                        updated_v = v.reserve_stock(quantity)
                        updated_list.append(updated_v)
                        found = True
                    else:
                        updated_list.append(v)

                if not found:
                    raise InsufficientStockError(
                        sku=normalized_vsku,
                        available=0,
                        requested=quantity,
                    )
                new_variants = tuple(updated_list)

        return replace(
            self,
            stock_quantity=self.stock_quantity - quantity,
            variants=new_variants,
        )

    def release_stock(
        self,
        quantity: int,
        variant_sku: str | None = None,
    ) -> "Product":
        """Restores or adds stock units to product inventory and specific variant."""
        if quantity <= 0:
            raise ValueError("Quantity to release must be strictly positive (> 0).")

        new_variants = self.variants
        if self.variants and variant_sku is not None and variant_sku.strip():
            normalized_vsku = variant_sku.strip().upper()
            updated_list: list[ProductVariant] = []
            for v in self.variants:
                if v.variant_sku == normalized_vsku:
                    updated_list.append(v.release_stock(quantity))
                else:
                    updated_list.append(v)
            new_variants = tuple(updated_list)

        return replace(
            self,
            stock_quantity=self.stock_quantity + quantity,
            variants=new_variants,
        )


def build_smart_bundle_recommendation(
    anchor_product: Product,
    catalog: list[Product],
    bundle_discount_pct: int = 12,
) -> dict[str, Any] | None:
    """Pure domain function identifying an active complement and guaranteeing 1.20x combined COGS floor."""
    if not (1 <= bundle_discount_pct <= 30):
        raise ValueError("bundle_discount_pct must be between 1 and 30.")

    eligible = [
        p
        for p in catalog
        if p.id != anchor_product.id
        and p.sku != anchor_product.sku
        and p.is_active
        and p.stock_quantity > 0
    ]
    if not eligible:
        return None

    best_complement: Product | None = None
    anchor_complements = set(anchor_product.complement_tags)
    if anchor_complements:
        for p in eligible:
            if p.category_tag in anchor_complements:
                best_complement = p
                break

    if best_complement is None:
        for p in eligible:
            if p.category_tag == anchor_product.category_tag:
                best_complement = p
                break

    if best_complement is None:
        best_complement = eligible[0]

    original_total_cents = anchor_product.price_cents + best_complement.price_cents
    combined_cogs_cents = anchor_product.unit_cost_cents + best_complement.unit_cost_cents
    min_protected_cents = (
        int((combined_cogs_cents * 120 + 99) // 100) if combined_cogs_cents > 0 else 1
    )

    nominal_discount = (original_total_cents * bundle_discount_pct) // 100
    tentative_price = original_total_cents - nominal_discount
    final_bundle_price = max(tentative_price, min_protected_cents)

    actual_savings = max(0, original_total_cents - final_bundle_price)
    effective_discount_pct = (
        round((actual_savings / original_total_cents) * 100.0, 1)
        if original_total_cents > 0
        else 0.0
    )

    return {
        "anchor_product_id": str(anchor_product.id),
        "anchor_sku": anchor_product.sku,
        "anchor_title": anchor_product.title,
        "anchor_price_cents": anchor_product.price_cents,
        "complement_product_id": str(best_complement.id),
        "complement_sku": best_complement.sku,
        "complement_title": best_complement.title,
        "complement_price_cents": best_complement.price_cents,
        "bundle_name": f"Combo Outfit IA: {anchor_product.title} + {best_complement.title}",
        "original_total_cents": original_total_cents,
        "bundle_price_cents": final_bundle_price,
        "savings_cents": actual_savings,
        "discount_percentage": effective_discount_pct,
        "combined_cogs_cents": combined_cogs_cents,
    }


@dataclass(frozen=True, kw_only=True)
class PromoCoupon:
    """Immutable domain entity representing a promotional discount coupon with COGS floor protection."""

    id: UUID = field(default_factory=uuid4)
    code: str
    discount_percentage: int
    is_active: bool = True
    times_used: int = 0
    max_uses: int | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def __post_init__(self) -> None:
        normalized_code = self.code.strip().upper()
        if not normalized_code:
            raise ValueError("PromoCoupon code cannot be empty.")
        object.__setattr__(self, "code", normalized_code)

        if not (1 <= self.discount_percentage <= 50):
            raise ValueError("PromoCoupon discount_percentage must be between 1 and 50.")
        if self.times_used < 0:
            raise ValueError("PromoCoupon times_used cannot be negative.")
        if self.max_uses is not None and self.max_uses <= 0:
            raise ValueError("PromoCoupon max_uses must be strictly positive when set.")

    def validate_can_apply(self) -> None:
        """Validates that the coupon is active and has remaining redemptions."""
        if not self.is_active:
            raise InvalidPromoCouponError(self.code, "Coupon is currently inactive.")
        if self.max_uses is not None and self.times_used >= self.max_uses:
            raise InvalidPromoCouponError(self.code, "Coupon usage limit has been reached.")

    def calculate_protected_discount_cents(
        self,
        items_subtotal_cents: int,
        total_cogs_cents: int,
    ) -> int:
        """Calculates discount while guaranteeing final price never drops below total_cogs_cents * 1.15."""
        self.validate_can_apply()
        if items_subtotal_cents <= 0:
            return 0
        raw_discount = (items_subtotal_cents * self.discount_percentage) // 100
        if total_cogs_cents > 0:
            min_protected_total = (total_cogs_cents * 115 + 99) // 100
            max_allowed_discount = max(0, items_subtotal_cents - min_protected_total)
            return min(raw_discount, max_allowed_discount)
        return min(raw_discount, items_subtotal_cents - 1)

    def record_redemption(self) -> "PromoCoupon":
        """Increments times_used by 1 after a successful order checkout."""
        self.validate_can_apply()
        return replace(self, times_used=self.times_used + 1)


@dataclass(frozen=True, kw_only=True)
class OrderItem:
    """Immutable value object representing a line item inside an Order."""

    product_id: UUID
    sku: str
    title: str
    unit_price_cents: int
    unit_cost_cents: int = 0
    quantity: int
    variant_sku: str | None = None

    def __post_init__(self) -> None:
        if self.variant_sku is not None:
            normalized_vsku = self.variant_sku.strip().upper()
            object.__setattr__(self, "variant_sku", normalized_vsku if normalized_vsku else None)
        if self.unit_price_cents <= 0:
            raise ValueError("OrderItem unit_price_cents must be strictly positive (> 0).")
        if self.unit_cost_cents < 0:
            raise ValueError("OrderItem unit_cost_cents cannot be negative.")
        if self.quantity <= 0:
            raise ValueError("OrderItem quantity must be strictly positive (> 0).")

    @property
    def subtotal_cents(self) -> int:
        """Calculates the line item revenue subtotal in integer cents."""
        return self.unit_price_cents * self.quantity

    @property
    def subtotal_cost_cents(self) -> int:
        """Calculates the line item COGS subtotal in integer cents."""
        return self.unit_cost_cents * self.quantity


@dataclass(frozen=True, kw_only=True)
class Order:
    """Immutable domain entity representing a buyer's purchase order with net profit calculation."""

    id: UUID = field(default_factory=uuid4)
    buyer_id: UUID
    items: tuple[OrderItem, ...]
    total_cents: int
    shipping_cost_cents: int = 0
    currency: str = "COP"
    payment_method: PaymentMethod
    status: OrderStatus = OrderStatus.PENDING_PAYMENT
    shipping_address: str
    idempotency_key: str
    source_job_id: UUID | None = None
    carrier_name: str | None = None
    tracking_code: str | None = None
    coupon_code: str | None = None
    discount_cents: int = 0
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def __post_init__(self) -> None:
        if not self.items:
            raise EmptyOrderError()
        if not isinstance(self.items, tuple):
            object.__setattr__(self, "items", tuple(self.items))

        if self.coupon_code is not None:
            cleaned_coupon = self.coupon_code.strip().upper()
            object.__setattr__(
                self,
                "coupon_code",
                cleaned_coupon if cleaned_coupon else None,
            )

        items_subtotal = sum(item.subtotal_cents for item in self.items)
        if self.discount_cents < 0 or self.discount_cents >= items_subtotal:
            raise ValueError(
                f"Order discount_cents ({self.discount_cents}) must be between 0 "
                f"and items_subtotal ({items_subtotal})."
            )

        expected_total = items_subtotal - self.discount_cents
        if self.total_cents != expected_total:
            raise ValueError(
                f"Order total_cents ({self.total_cents}) does not match "
                f"items sum minus discount ({expected_total})."
            )
        if self.shipping_cost_cents < 0:
            raise ValueError("Order shipping_cost_cents cannot be negative.")
        if not self.shipping_address.strip():
            raise ValueError("Order shipping_address cannot be empty.")
        if not self.idempotency_key.strip():
            raise ValueError("Order idempotency_key cannot be empty.")

    @property
    def subtotal_before_discount_cents(self) -> int:
        """Gross subtotal of all items before applying any promotional coupon discount."""
        return sum(item.subtotal_cents for item in self.items)

    @property
    def total_cogs_cents(self) -> int:
        """Total Cost of Goods Sold (COGS) across all items in the order."""
        return sum(item.subtotal_cost_cents for item in self.items)

    @property
    def net_profit_cents(self) -> int:
        """Realized net profit in cents after subtracting COGS and shipping cost."""
        return self.total_cents - self.total_cogs_cents - self.shipping_cost_cents

    def mark_shipped(self, carrier_name: str, tracking_code: str) -> "Order":
        """Transitions a CONFIRMED order to SHIPPED with carrier and tracking guide."""
        if self.status != OrderStatus.CONFIRMED:
            raise InvalidOrderStateTransitionError(
                current_status=self.status.value,
                target_status=OrderStatus.SHIPPED.value,
            )
        cleaned_carrier = carrier_name.strip()
        cleaned_tracking = tracking_code.strip()
        if not cleaned_carrier:
            raise ValueError("carrier_name cannot be empty when shipping an order.")
        if not cleaned_tracking:
            raise ValueError("tracking_code cannot be empty when shipping an order.")
        return replace(
            self,
            status=OrderStatus.SHIPPED,
            carrier_name=cleaned_carrier,
            tracking_code=cleaned_tracking,
        )

    def mark_delivered(self) -> "Order":
        """Transitions a confirmed/shipped order to DELIVERED."""
        if self.status in {OrderStatus.CANCELLED, OrderStatus.DELIVERED}:
            raise InvalidOrderStateTransitionError(
                current_status=self.status.value,
                target_status=OrderStatus.DELIVERED.value,
            )
        return replace(self, status=OrderStatus.DELIVERED)


def build_customer_lifecycle_messages(order: Order) -> dict[str, str]:
    """Generates the 3 personalized post-sale customer messages (Confirmation, Shipping, Post-Delivery)."""
    short_id = str(order.id)[:8]
    items_summary = ", ".join(
        f"{item.quantity}x {item.title}" for item in order.items
    )
    total_cop = f"${order.total_cents // 100:,} {order.currency}"
    is_cod = order.payment_method == PaymentMethod.CASH_ON_DELIVERY
    payment_label = (
        "Pago Contraentrega (COD)"
        if is_cod
        else "Pagado con Billetera Super App"
    )

    confirmation_msg = (
        f"✅ ¡Hola! Confirmamos tu pedido #{short_id} en Super App.\n"
        f"• Productos: {items_summary}\n"
        f"• Total: {total_cop}\n"
        f"• Modalidad: {payment_label}\n"
        f"• Dirección de despacho: {order.shipping_address}\n"
        "Te avisaremos apenas salga a ruta con tu número de guía."
    )

    carrier_label = order.carrier_name or "Transportadora Aliada"
    tracking_label = order.tracking_code or "PENDIENTE-ASIGNACION"
    cod_reminder = (
        f"\n💡 Recordatorio Contraentrega: Ten listo el efectivo exacto ({total_cop}) al recibir tu paquete."
        if is_cod
        else "\n💳 Tu pedido ya se encuentra 100% pagado con Billetera Super App."
    )
    shipping_msg = (
        f"🚚 ¡Tu pedido #{short_id} ya va en camino!\n"
        f"• Transportadora: {carrier_label}\n"
        f"• Número de guía: {tracking_label}\n"
        f"• Destino: {order.shipping_address}"
        f"{cod_reminder}"
    )

    post_delivery_msg = (
        f"🎉 ¡Gracias por tu compra #{short_id} en Super App!\n"
        f"Esperamos que disfrutes mucho: {items_summary}.\n"
        "• Soporte directo WhatsApp: https://wa.me/573000000000\n"
        "• 🎁 Regalo de Recompra: Usa el cupón SUPER10 en tu próximo pedido para un 10% OFF."
    )

    return {
        "confirmation_msg": confirmation_msg,
        "shipping_msg": shipping_msg,
        "post_delivery_msg": post_delivery_msg,
    }
