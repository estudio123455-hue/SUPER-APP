"""Application Use Cases for the Commerce bounded context (Layer 2)."""

import asyncio
from uuid import UUID

from app.core.event_bus import InMemoryEventBus
from app.modules.commerce.application.dtos import (
    ApplyDynamicPricingCommand,
    CommerceFinancialSummaryDTO,
    CreateProductCommand,
    CreatePromoCouponCommand,
    CrossSellBundleDTO,
    DynamicPriceResultDTO,
    OrderDTO,
    OrderLifecycleMessagesDTO,
    PlaceOrderCommand,
    ProductDTO,
    PromoCouponDTO,
    RestockProductCommand,
    ShipOrderCommand,
)
from app.modules.commerce.application.events import (
    OrderDeliveredAndSettledEvent,
    OrderPaidEvent,
    OrderPlacedEvent,
    OrderShippedEvent,
    ProductCreatedEvent,
    ProductPriceAdjustedEvent,
)
from app.modules.commerce.domain.entities import (
    Order,
    OrderItem,
    OrderStatus,
    PaymentMethod,
    Product,
    PromoCoupon,
    build_smart_bundle_recommendation,
)
from app.modules.commerce.domain.exceptions import (
    DuplicateSkuError,
    EmptyOrderError,
    InvalidPromoCouponError,
    OrderNotFoundError,
    OrderPaymentFailedError,
    ProductNotFoundError,
)
from app.modules.commerce.domain.repositories import (
    OrderRepository,
    ProductRepository,
    PromoCouponRepository,
    WalletPaymentPort,
)


class CreateProductUseCase:
    """Validates SKU uniqueness, persists a new Product, and emits ProductCreatedEvent."""

    def __init__(
        self,
        product_repository: ProductRepository,
        event_bus: InMemoryEventBus,
    ) -> None:
        self._product_repository = product_repository
        self._event_bus = event_bus

    async def execute(self, command: CreateProductCommand) -> ProductDTO:
        normalized_sku = command.sku.strip().upper()
        existing = await self._product_repository.get_by_sku(normalized_sku)
        if existing is not None:
            raise DuplicateSkuError(normalized_sku)

        product = Product(
            merchant_id=command.merchant_id,
            sku=normalized_sku,
            title=command.title.strip(),
            description=command.description.strip(),
            price_cents=command.price_cents,
            unit_cost_cents=command.unit_cost_cents,
            stock_quantity=command.stock_quantity,
            variants=command.variants,
            category_tag=command.category_tag,
            complement_tags=command.complement_tags,
            is_active=True,
        )
        saved = await self._product_repository.save(product)

        await self._event_bus.publish(
            ProductCreatedEvent(
                product_id=saved.id,
                merchant_id=saved.merchant_id,
                sku=saved.sku,
                title=saved.title,
                price_cents=saved.price_cents,
                unit_cost_cents=saved.unit_cost_cents,
                stock_quantity=saved.stock_quantity,
            )
        )
        return ProductDTO.from_entity(saved)


class RestockProductUseCase:
    """Adds inventory units to an existing catalog product."""

    def __init__(self, product_repository: ProductRepository) -> None:
        self._product_repository = product_repository

    async def execute(self, command: RestockProductCommand) -> ProductDTO:
        product = await self._product_repository.get_by_id(command.product_id)
        if product is None:
            raise ProductNotFoundError(str(command.product_id))

        restocked_product = product.release_stock(command.quantity_to_add)
        saved = await self._product_repository.save(restocked_product)
        return ProductDTO.from_entity(saved)


class ApplyDynamicPricingUseCase:
    """Adjusts a product's price based on stock and demand while enforcing the 25% margin floor."""

    def __init__(
        self,
        product_repository: ProductRepository,
        event_bus: InMemoryEventBus,
    ) -> None:
        self._product_repository = product_repository
        self._event_bus = event_bus

    async def execute(
        self,
        command: ApplyDynamicPricingCommand,
    ) -> DynamicPriceResultDTO:
        product = await self._product_repository.get_by_id(command.product_id)
        if product is None:
            raise ProductNotFoundError(str(command.product_id))

        old_price = product.price_cents
        adjusted_product, strategy = product.apply_dynamic_pricing(
            demand_conversions=command.demand_conversions
        )
        saved = await self._product_repository.save(adjusted_product)

        await self._event_bus.publish(
            ProductPriceAdjustedEvent(
                product_id=saved.id,
                sku=saved.sku,
                old_price_cents=old_price,
                new_price_cents=saved.price_cents,
                pricing_strategy=strategy,
                margin_percentage=saved.margin_percentage,
            )
        )

        return DynamicPriceResultDTO(
            product=ProductDTO.from_entity(saved),
            old_price_cents=old_price,
            new_price_cents=saved.price_cents,
            pricing_strategy=strategy,
        )


class ListCatalogUseCase:
    """Lists active catalog products that currently have available inventory, with optional search and category filters."""

    def __init__(self, product_repository: ProductRepository) -> None:
        self._product_repository = product_repository

    async def execute(
        self,
        search: str | None = None,
        category_tag: str | None = None,
    ) -> list[ProductDTO]:
        products = await self._product_repository.list_active()
        if category_tag is not None and category_tag.strip():
            normalized_tag = category_tag.strip().upper()
            products = [
                p for p in products if p.category_tag.strip().upper() == normalized_tag
            ]
        if search is not None and search.strip():
            query = search.strip().lower()
            products = [
                p
                for p in products
                if query in p.title.lower() or query in p.sku.lower()
            ]
        return [ProductDTO.from_entity(p) for p in products]



class GetCrossSellBundleUseCase:
    """Calculates and returns a smart AI cross-sell bundle recommendation protecting COGS floor."""

    def __init__(self, product_repository: ProductRepository) -> None:
        self._product_repository = product_repository

    async def execute(
        self,
        product_id: UUID,
        bundle_discount_pct: int = 12,
    ) -> CrossSellBundleDTO | None:
        anchor = await self._product_repository.get_by_id(product_id)
        if anchor is None or not anchor.is_active:
            return None
        catalog = await self._product_repository.list_active()
        bundle_dict = build_smart_bundle_recommendation(
            anchor_product=anchor,
            catalog=catalog,
            bundle_discount_pct=bundle_discount_pct,
        )
        if bundle_dict is None:
            return None
        return CrossSellBundleDTO(
            anchor_product_id=UUID(bundle_dict["anchor_product_id"]),
            anchor_sku=bundle_dict["anchor_sku"],
            anchor_title=bundle_dict["anchor_title"],
            anchor_price_cents=bundle_dict["anchor_price_cents"],
            complement_product_id=UUID(bundle_dict["complement_product_id"]),
            complement_sku=bundle_dict["complement_sku"],
            complement_title=bundle_dict["complement_title"],
            complement_price_cents=bundle_dict["complement_price_cents"],
            bundle_name=bundle_dict["bundle_name"],
            original_total_cents=bundle_dict["original_total_cents"],
            bundle_price_cents=bundle_dict["bundle_price_cents"],
            savings_cents=bundle_dict["savings_cents"],
            discount_percentage=bundle_dict["discount_percentage"],
            combined_cogs_cents=bundle_dict["combined_cogs_cents"],
        )


class CreatePromoCouponUseCase:
    """Creates or updates a promotional coupon with COGS floor protection."""

    def __init__(self, coupon_repository: PromoCouponRepository) -> None:
        self._coupon_repository = coupon_repository

    async def execute(self, command: CreatePromoCouponCommand) -> PromoCouponDTO:
        coupon = PromoCoupon(
            code=command.code,
            discount_percentage=command.discount_percentage,
            is_active=True,
            times_used=0,
            max_uses=command.max_uses,
        )
        saved = await self._coupon_repository.save(coupon)
        return PromoCouponDTO.from_entity(saved)


class ListPromoCouponsUseCase:
    """Lists all promotional coupons available in the store."""

    def __init__(self, coupon_repository: PromoCouponRepository) -> None:
        self._coupon_repository = coupon_repository

    async def execute(self) -> list[PromoCouponDTO]:
        coupons = await self._coupon_repository.list_all()
        return [PromoCouponDTO.from_entity(c) for c in coupons]


_PLACE_ORDER_LOCK: asyncio.Lock = asyncio.Lock()


class PlaceOrderUseCase:
    """Orchestrates stock reservation, promo coupon discount with COGS floor, wallet/COD payment, and events."""

    def __init__(
        self,
        product_repository: ProductRepository,
        order_repository: OrderRepository,
        wallet_payment_port: WalletPaymentPort,
        event_bus: InMemoryEventBus,
        coupon_repository: PromoCouponRepository | None = None,
    ) -> None:
        self._product_repository = product_repository
        self._order_repository = order_repository
        self._wallet_payment_port = wallet_payment_port
        self._event_bus = event_bus
        self._coupon_repository = coupon_repository

    async def _rollback_reserved_stock(
        self,
        reserved_records: list[tuple[Product, int, str | None]],
    ) -> None:
        for reserved_product, quantity, variant_sku in reserved_records:
            restored = reserved_product.release_stock(quantity, variant_sku)
            await self._product_repository.save(restored)

    async def execute(self, command: PlaceOrderCommand) -> OrderDTO:
        async with _PLACE_ORDER_LOCK:
            if hasattr(self._product_repository, "_session"):
                self._product_repository._session.expire_all()

            normalized_key = command.idempotency_key.strip()
            if not normalized_key:
                raise ValueError("Order idempotency_key cannot be empty.")

            # 1. Idempotency check
            existing_order = await self._order_repository.get_by_idempotency_key(
                normalized_key
            )
            if existing_order is not None:
                return OrderDTO.from_entity(existing_order)

            if not command.items:
                raise EmptyOrderError()

            reserved_records: list[tuple[Product, int, str | None]] = []
            order_items: list[OrderItem] = []

            # 2. Verify product existence and reserve stock atomically
            try:
                for item_req in command.items:
                    product = await self._product_repository.get_by_id(item_req.product_id)
                    if product is None or not product.is_active:
                        raise ProductNotFoundError(str(item_req.product_id))

                    reserved_product = product.reserve_stock(
                        item_req.quantity,
                        variant_sku=item_req.variant_sku,
                    )
                    saved_product = await self._product_repository.save(reserved_product)
                    reserved_records.append(
                        (saved_product, item_req.quantity, item_req.variant_sku)
                    )

                    order_items.append(
                        OrderItem(
                            product_id=product.id,
                            sku=product.sku,
                            title=product.title,
                            unit_price_cents=product.price_cents,
                            unit_cost_cents=product.unit_cost_cents,
                            quantity=item_req.quantity,
                            variant_sku=item_req.variant_sku,
                        )
                    )
            except Exception:
                if reserved_records:
                    await self._rollback_reserved_stock(reserved_records)
                raise

            items_subtotal_cents = sum(i.subtotal_cents for i in order_items)
            total_cogs_cents = sum(i.subtotal_cost_cents for i in order_items)
            applied_coupon: PromoCoupon | None = None
            discount_cents = 0

            if command.coupon_code is not None and command.coupon_code.strip():
                cleaned_code = command.coupon_code.strip().upper()
                try:
                    if self._coupon_repository is not None:
                        applied_coupon = await self._coupon_repository.get_by_code(
                            cleaned_code
                        )
                    elif cleaned_code == "SUPER10":
                        applied_coupon = PromoCoupon(
                            code="SUPER10",
                            discount_percentage=10,
                        )

                    if applied_coupon is None:
                        raise InvalidPromoCouponError(
                            cleaned_code,
                            "Coupon code does not exist.",
                        )

                    discount_cents = applied_coupon.calculate_protected_discount_cents(
                        items_subtotal_cents=items_subtotal_cents,
                        total_cogs_cents=total_cogs_cents,
                    )
                except Exception:
                    await self._rollback_reserved_stock(reserved_records)
                    raise

            total_cents = items_subtotal_cents - discount_cents

            # Check buyer VIP loyalty tier for automatic Free Shipping (SILVER / GOLD)
            effective_shipping_cents = command.shipping_cost_cents
            try:
                buyer_tier = await self._wallet_payment_port.get_loyalty_tier(command.buyer_id)
                if str(buyer_tier).upper() in ("SILVER", "GOLD"):
                    effective_shipping_cents = 0
            except Exception:
                pass

            # 3. Process payment according to payment_method
            if command.payment_method == PaymentMethod.WALLET:
                try:
                    await self._wallet_payment_port.charge(
                        buyer_id=command.buyer_id,
                        amount_cents=total_cents,
                        reference=f"Commerce Order ({normalized_key})",
                        idempotency_key=f"commerce-order-{normalized_key}",
                    )
                except OrderPaymentFailedError:
                    await self._rollback_reserved_stock(reserved_records)
                    raise

                if applied_coupon is not None and self._coupon_repository is not None:
                    await self._coupon_repository.save(applied_coupon.record_redemption())

                order = Order(
                    buyer_id=command.buyer_id,
                    items=tuple(order_items),
                    total_cents=total_cents,
                    shipping_cost_cents=effective_shipping_cents,
                    currency="COP",
                    payment_method=PaymentMethod.WALLET,
                    status=OrderStatus.CONFIRMED,
                    shipping_address=command.shipping_address.strip(),
                    idempotency_key=normalized_key,
                    source_job_id=command.source_job_id,
                    coupon_code=applied_coupon.code if applied_coupon else None,
                    discount_cents=discount_cents,
                )
                saved_order = await self._order_repository.save(order)

                await self._event_bus.publish(
                    OrderPaidEvent(
                        order_id=saved_order.id,
                        buyer_id=saved_order.buyer_id,
                        total_cents=saved_order.total_cents,
                        currency=saved_order.currency,
                        payment_method=saved_order.payment_method.value,
                        idempotency_key=saved_order.idempotency_key,
                        source_job_id=saved_order.source_job_id,
                    )
                )
                return OrderDTO.from_entity(saved_order)

            if command.payment_method == PaymentMethod.CASH_ON_DELIVERY:
                if applied_coupon is not None and self._coupon_repository is not None:
                    await self._coupon_repository.save(applied_coupon.record_redemption())

                order = Order(
                    buyer_id=command.buyer_id,
                    items=tuple(order_items),
                    total_cents=total_cents,
                    shipping_cost_cents=effective_shipping_cents,
                    currency="COP",
                    payment_method=PaymentMethod.CASH_ON_DELIVERY,
                    status=OrderStatus.CONFIRMED,
                    shipping_address=command.shipping_address.strip(),
                    idempotency_key=normalized_key,
                    source_job_id=command.source_job_id,
                    coupon_code=applied_coupon.code if applied_coupon else None,
                    discount_cents=discount_cents,
                )
                saved_order = await self._order_repository.save(order)

                await self._event_bus.publish(
                    OrderPlacedEvent(
                        order_id=saved_order.id,
                        buyer_id=saved_order.buyer_id,
                        total_cents=saved_order.total_cents,
                        currency=saved_order.currency,
                        payment_method=saved_order.payment_method.value,
                        idempotency_key=saved_order.idempotency_key,
                        source_job_id=saved_order.source_job_id,
                    )
                )
                return OrderDTO.from_entity(saved_order)

            await self._rollback_reserved_stock(reserved_records)
            raise ValueError(f"Unsupported payment method: {command.payment_method}")


class ShipOrderUseCase:
    """Marks a CONFIRMED order as SHIPPED with carrier & tracking guide and emits OrderShippedEvent."""

    def __init__(
        self,
        order_repository: OrderRepository,
        event_bus: InMemoryEventBus,
    ) -> None:
        self._order_repository = order_repository
        self._event_bus = event_bus

    async def execute(self, command: ShipOrderCommand) -> OrderDTO:
        order = await self._order_repository.get_by_id(command.order_id)
        if order is None:
            raise OrderNotFoundError(str(command.order_id))

        shipped_order = order.mark_shipped(
            carrier_name=command.carrier_name,
            tracking_code=command.tracking_code,
        )
        saved_order = await self._order_repository.save(shipped_order)

        await self._event_bus.publish(
            OrderShippedEvent(
                order_id=saved_order.id,
                buyer_id=saved_order.buyer_id,
                carrier_name=saved_order.carrier_name or "",
                tracking_code=saved_order.tracking_code or "",
                payment_method=saved_order.payment_method.value,
                total_cents=saved_order.total_cents,
                shipping_address=saved_order.shipping_address,
            )
        )
        return OrderDTO.from_entity(saved_order)


class GetOrderLifecycleMessagesUseCase:
    """Builds the 3 automated post-sale customer messages and direct wa.me links for an Order."""

    def __init__(self, order_repository: OrderRepository) -> None:
        self._order_repository = order_repository

    async def execute(self, order_id: UUID) -> OrderLifecycleMessagesDTO:
        order = await self._order_repository.get_by_id(order_id)
        if order is None:
            raise OrderNotFoundError(str(order_id))
        return OrderLifecycleMessagesDTO.from_entity(order)


class MarkOrderDeliveredUseCase:
    """Marks a confirmed order as DELIVERED and emits OrderDeliveredAndSettledEvent."""

    def __init__(
        self,
        order_repository: OrderRepository,
        product_repository: ProductRepository,
        event_bus: InMemoryEventBus,
    ) -> None:
        self._order_repository = order_repository
        self._product_repository = product_repository
        self._event_bus = event_bus

    async def execute(self, order_id: UUID, acting_user_id: UUID) -> OrderDTO:
        order = await self._order_repository.get_by_id(order_id)
        if order is None:
            raise OrderNotFoundError(str(order_id))

        delivered_order = order.mark_delivered()
        saved_order = await self._order_repository.save(delivered_order)

        merchant_id = acting_user_id
        if saved_order.items:
            first_prod = await self._product_repository.get_by_id(
                saved_order.items[0].product_id
            )
            if first_prod is not None:
                merchant_id = first_prod.merchant_id

        await self._event_bus.publish(
            OrderDeliveredAndSettledEvent(
                order_id=saved_order.id,
                merchant_id=merchant_id,
                buyer_id=saved_order.buyer_id,
                payment_method=saved_order.payment_method.value,
                gross_total_cents=saved_order.total_cents,
                total_cogs_cents=saved_order.total_cogs_cents,
                shipping_cost_cents=saved_order.shipping_cost_cents,
                net_profit_cents=saved_order.net_profit_cents,
                source_job_id=saved_order.source_job_id,
            )
        )

        return OrderDTO.from_entity(saved_order)


class GetCommerceFinancialSummaryUseCase:
    """Calculates inventory valuation at cost/retail and realized net profit."""

    def __init__(
        self,
        product_repository: ProductRepository,
        order_repository: OrderRepository,
    ) -> None:
        self._product_repository = product_repository
        self._order_repository = order_repository

    async def execute(self, user_id: UUID) -> CommerceFinancialSummaryDTO:
        products = await self._product_repository.list_active()
        orders = await self._order_repository.list_by_buyer(user_id)

        inv_cost = sum(p.stock_quantity * p.unit_cost_cents for p in products)
        inv_retail = sum(p.stock_quantity * p.price_cents for p in products)

        active_orders = [o for o in orders if o.status != OrderStatus.CANCELLED]
        delivered_count = sum(
            1 for o in active_orders if o.status == OrderStatus.DELIVERED
        )
        gross_revenue = sum(o.total_cents for o in active_orders)
        acc_cogs = sum(o.total_cogs_cents for o in active_orders)
        acc_shipping = sum(o.shipping_cost_cents for o in active_orders)
        net_profit = sum(o.net_profit_cents for o in active_orders)

        return CommerceFinancialSummaryDTO(
            inventory_cost_value_cents=inv_cost,
            inventory_retail_value_cents=inv_retail,
            potential_inventory_profit_cents=inv_retail - inv_cost,
            orders_count=len(active_orders),
            delivered_orders_count=delivered_count,
            gross_revenue_cents=gross_revenue,
            accumulated_cogs_cents=acc_cogs,
            accumulated_shipping_cents=acc_shipping,
            realized_net_profit_cents=net_profit,
        )


class ListBuyerOrdersUseCase:
    """Lists purchase history for a specific buyer."""

    def __init__(self, order_repository: OrderRepository) -> None:
        self._order_repository = order_repository

    async def execute(self, buyer_id: UUID) -> list[OrderDTO]:
        orders = await self._order_repository.list_by_buyer(buyer_id)
        return [OrderDTO.from_entity(o) for o in orders]


class GenerateWeeklyExecutiveReportUseCase:
    """Generates a downloadable Markdown executive report with Unit Economics, Dynamic Pricing & Attribution."""

    def __init__(
        self,
        product_repository: ProductRepository,
        order_repository: OrderRepository,
    ) -> None:
        self._product_repository = product_repository
        self._order_repository = order_repository

    async def execute(self, user_id: UUID) -> str:
        products = await self._product_repository.list_active()
        orders = await self._order_repository.list_by_buyer(user_id)

        inv_cost = sum(p.stock_quantity * p.unit_cost_cents for p in products)
        inv_retail = sum(p.stock_quantity * p.price_cents for p in products)
        pot_profit = inv_retail - inv_cost
        avg_margin = (
            round(sum(p.margin_percentage for p in products) / len(products), 2)
            if products
            else 0.0
        )

        active_orders = [o for o in orders if o.status != OrderStatus.CANCELLED]
        delivered_orders = [
            o for o in active_orders if o.status == OrderStatus.DELIVERED
        ]
        wallet_orders = [
            o for o in active_orders if o.payment_method == PaymentMethod.WALLET
        ]
        cod_orders = [
            o
            for o in active_orders
            if o.payment_method == PaymentMethod.CASH_ON_DELIVERY
        ]
        attributed_orders = [
            o for o in active_orders if o.source_job_id is not None
        ]

        gross_rev = sum(o.total_cents for o in active_orders)
        total_cogs = sum(o.total_cogs_cents for o in active_orders)
        total_ship = sum(o.shipping_cost_cents for o in active_orders)
        net_profit = sum(o.net_profit_cents for o in active_orders)

        lines = [
            "# 📊 Reporte Ejecutivo Semanal — Super App Ecosystem",
            "",
            "## 1. Resumen de Unidad Económica (COP)",
            f"- **Valor del Inventario en Casa (al Costo COGS):** ${inv_cost // 100:,} COP",
            f"- **Valor de Venta Potencial (Retail):** ${inv_retail // 100:,} COP",
            f"- **Utilidad Potencial en Inventario:** ${pot_profit // 100:,} COP",
            f"- **Margen Bruto Promedio del Catálogo:** {avg_margin}%",
            f"- **Ingresos Brutos Acumulados:** ${gross_rev // 100:,} COP",
            f"- **Costo de Mercancía Vendida (COGS):** ${total_cogs // 100:,} COP",
            f"- **Total Costos de Envío:** ${total_ship // 100:,} COP",
            f"- **Utilidad Neta Realizada:** ${net_profit // 100:,} COP",
            "",
            "## 2. Estado de Inventario y Recomendaciones de Precios Dinámicos",
            "| SKU | Producto | Precio Actual | COGS | Margen % | Stock | Estrategia Recomendada | Precio Sugerido |",
            "| :--- | :--- | ---: | ---: | ---: | ---: | :--- | ---: |",
        ]

        for p in products:
            suggested_prod, strategy = p.apply_dynamic_pricing(
                demand_conversions=len(attributed_orders)
            )
            lines.append(
                f"| `{p.sku}` | {p.title} | ${p.price_cents // 100:,} COP | "
                f"${p.unit_cost_cents // 100:,} COP | {p.margin_percentage}% | "
                f"{p.stock_quantity} | `{strategy}` | ${suggested_prod.price_cents // 100:,} COP |"
            )

        lines.extend(
            [
                "",
                "## 3. Desglose de Órdenes, Pagos y Atribución por Video (`source_job_id`)",
                f"- **Total Órdenes Activas:** {len(active_orders)}",
                f"- **Órdenes Entregadas y Liquidadas (`DELIVERED`):** {len(delivered_orders)}",
                f"- **Pagadas con Billetera (`WALLET`):** {len(wallet_orders)}",
                f"- **Pago Contraentrega (`CASH_ON_DELIVERY`):** {len(cod_orders)}",
                f"- **Órdenes Atribuidas a Videos de IA (`source_job_id`):** {len(attributed_orders)}",
            ]
        )

        return "\n".join(lines) + "\n"
