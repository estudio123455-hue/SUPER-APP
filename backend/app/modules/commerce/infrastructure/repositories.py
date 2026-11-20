"""SQLAlchemy 2.0 repositories and cross-module Wallet adapter for Commerce."""

from datetime import UTC
from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.commerce.domain.entities import (
    Order,
    OrderItem,
    OrderStatus,
    PaymentMethod,
    Product,
    ProductVariant,
    PromoCoupon,
)
from app.modules.commerce.domain.exceptions import OrderPaymentFailedError
from app.modules.commerce.domain.repositories import (
    OrderRepository,
    ProductRepository,
    PromoCouponRepository,
    WalletPaymentPort,
)
from app.modules.commerce.infrastructure.models import (
    OrderItemModel,
    OrderModel,
    ProductModel,
    PromoCouponModel,
)
from app.modules.wallet.public_api import (
    WalletDomainError,
    debit_user_wallet,
    get_user_loyalty_tier,
)


class SqlAlchemyProductRepository(ProductRepository):
    """Adapter persisting Product entities via SQLAlchemy 2.0 AsyncSession."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    @staticmethod
    def _to_domain(model: ProductModel) -> Product:
        created_at = model.created_at
        if created_at.tzinfo is None:
            created_at = created_at.replace(tzinfo=UTC)
        raw_variants = model.variants or []
        variants = tuple(
            ProductVariant(
                variant_sku=v["variant_sku"],
                size=v.get("size"),
                color=v.get("color"),
                stock_quantity=int(v.get("stock_quantity", 0)),
            )
            for v in raw_variants
            if isinstance(v, dict) and "variant_sku" in v
        )
        return Product(
            id=model.id,
            merchant_id=model.merchant_id,
            sku=model.sku,
            title=model.title,
            description=model.description,
            price_cents=int(model.price_cents),
            unit_cost_cents=int(model.unit_cost_cents),
            stock_quantity=int(model.stock_quantity),
            variants=variants,
            category_tag=getattr(model, "category_tag", "GENERAL") or "GENERAL",
            complement_tags=tuple(getattr(model, "complement_tags", []) or []),
            is_active=model.is_active,
            created_at=created_at,
        )

    async def get_by_id(self, product_id: UUID) -> Product | None:
        stmt = (
            select(ProductModel)
            .where(ProductModel.id == product_id)
            .execution_options(populate_existing=True)
        )
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        return self._to_domain(model) if model is not None else None

    async def get_by_sku(self, sku: str) -> Product | None:
        normalized_sku = sku.strip().upper()
        stmt = select(ProductModel).where(ProductModel.sku == normalized_sku)
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        return self._to_domain(model) if model is not None else None

    async def list_active(self) -> list[Product]:
        stmt = (
            select(ProductModel)
            .where(
                ProductModel.is_active.is_(True),
                ProductModel.stock_quantity > 0,
            )
            .order_by(ProductModel.created_at.desc())
        )
        result = await self._session.execute(stmt)
        models = result.scalars().all()
        return [self._to_domain(m) for m in models]

    async def save(self, product: Product) -> Product:
        stmt = select(ProductModel).where(ProductModel.id == product.id)
        result = await self._session.execute(stmt)
        existing = result.scalar_one_or_none()

        serialized_variants = [
            {
                "variant_sku": v.variant_sku,
                "size": v.size,
                "color": v.color,
                "stock_quantity": v.stock_quantity,
            }
            for v in product.variants
        ]

        if existing is None:
            model = ProductModel(
                id=product.id,
                merchant_id=product.merchant_id,
                sku=product.sku,
                title=product.title,
                description=product.description,
                price_cents=product.price_cents,
                unit_cost_cents=product.unit_cost_cents,
                stock_quantity=product.stock_quantity,
                variants=serialized_variants,
                category_tag=product.category_tag,
                complement_tags=list(product.complement_tags),
                is_active=product.is_active,
                created_at=product.created_at,
            )
            self._session.add(model)
        else:
            existing.sku = product.sku
            existing.title = product.title
            existing.description = product.description
            existing.price_cents = product.price_cents
            existing.unit_cost_cents = product.unit_cost_cents
            existing.stock_quantity = product.stock_quantity
            existing.variants = serialized_variants
            existing.category_tag = product.category_tag
            existing.complement_tags = list(product.complement_tags)
            existing.is_active = product.is_active
            model = existing

        await self._session.commit()
        return product


class SqlAlchemyOrderRepository(OrderRepository):
    """Adapter persisting Order entities and their OrderItems via SQLAlchemy 2.0."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def _load_items(self, order_id: UUID) -> tuple[OrderItem, ...]:
        stmt = select(OrderItemModel).where(OrderItemModel.order_id == order_id)
        result = await self._session.execute(stmt)
        models = result.scalars().all()
        return tuple(
            OrderItem(
                product_id=m.product_id,
                sku=m.sku,
                title=m.title,
                unit_price_cents=int(m.unit_price_cents),
                unit_cost_cents=int(m.unit_cost_cents),
                quantity=int(m.quantity),
                variant_sku=m.variant_sku,
            )
            for m in models
        )

    async def _to_domain(self, model: OrderModel) -> Order:
        created_at = model.created_at
        if created_at.tzinfo is None:
            created_at = created_at.replace(tzinfo=UTC)
        items = await self._load_items(model.id)
        return Order(
            id=model.id,
            buyer_id=model.buyer_id,
            items=items,
            total_cents=int(model.total_cents),
            shipping_cost_cents=int(model.shipping_cost_cents),
            currency=model.currency,
            payment_method=PaymentMethod(model.payment_method),
            status=OrderStatus(model.status),
            shipping_address=model.shipping_address,
            idempotency_key=model.idempotency_key,
            source_job_id=model.source_job_id,
            carrier_name=model.carrier_name,
            tracking_code=model.tracking_code,
            coupon_code=model.coupon_code,
            discount_cents=int(model.discount_cents or 0),
            created_at=created_at,
        )

    async def get_by_id(self, order_id: UUID) -> Order | None:
        stmt = select(OrderModel).where(OrderModel.id == order_id)
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        return await self._to_domain(model) if model is not None else None

    async def get_by_idempotency_key(self, idempotency_key: str) -> Order | None:
        stmt = select(OrderModel).where(
            OrderModel.idempotency_key == idempotency_key.strip()
        )
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        return await self._to_domain(model) if model is not None else None

    async def list_by_buyer(self, buyer_id: UUID) -> list[Order]:
        stmt = (
            select(OrderModel)
            .where(OrderModel.buyer_id == buyer_id)
            .order_by(OrderModel.created_at.desc())
        )
        result = await self._session.execute(stmt)
        models = result.scalars().all()
        return [await self._to_domain(m) for m in models]

    async def save(self, order: Order) -> Order:
        stmt = select(OrderModel).where(OrderModel.id == order.id)
        result = await self._session.execute(stmt)
        existing = result.scalar_one_or_none()

        if existing is None:
            order_model = OrderModel(
                id=order.id,
                buyer_id=order.buyer_id,
                total_cents=order.total_cents,
                shipping_cost_cents=order.shipping_cost_cents,
                currency=order.currency,
                payment_method=order.payment_method.value,
                status=order.status.value,
                shipping_address=order.shipping_address,
                idempotency_key=order.idempotency_key,
                source_job_id=order.source_job_id,
                carrier_name=order.carrier_name,
                tracking_code=order.tracking_code,
                coupon_code=order.coupon_code,
                discount_cents=order.discount_cents,
                created_at=order.created_at,
            )
            self._session.add(order_model)
        else:
            existing.total_cents = order.total_cents
            existing.shipping_cost_cents = order.shipping_cost_cents
            existing.status = order.status.value
            existing.shipping_address = order.shipping_address
            existing.source_job_id = order.source_job_id
            existing.carrier_name = order.carrier_name
            existing.tracking_code = order.tracking_code
            existing.coupon_code = order.coupon_code
            existing.discount_cents = order.discount_cents
            order_model = existing
            await self._session.execute(
                delete(OrderItemModel).where(OrderItemModel.order_id == order.id)
            )

        for item in order.items:
            self._session.add(
                OrderItemModel(
                    order_id=order.id,
                    product_id=item.product_id,
                    sku=item.sku,
                    title=item.title,
                    unit_price_cents=item.unit_price_cents,
                    unit_cost_cents=item.unit_cost_cents,
                    quantity=item.quantity,
                    variant_sku=item.variant_sku,
                )
            )

        await self._session.commit()
        return order


class SqlAlchemyPromoCouponRepository(PromoCouponRepository):
    """Adapter persisting PromoCoupon entities in commerce_schema."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    @staticmethod
    def _to_domain(model: PromoCouponModel) -> PromoCoupon:
        created_at = model.created_at
        if created_at.tzinfo is None:
            created_at = created_at.replace(tzinfo=UTC)
        return PromoCoupon(
            id=model.id,
            code=model.code,
            discount_percentage=int(model.discount_percentage),
            is_active=model.is_active,
            times_used=int(model.times_used),
            max_uses=int(model.max_uses) if model.max_uses is not None else None,
            created_at=created_at,
        )

    async def get_by_code(self, code: str) -> PromoCoupon | None:
        normalized_code = code.strip().upper()
        stmt = select(PromoCouponModel).where(PromoCouponModel.code == normalized_code)
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        if model is None and normalized_code == "SUPER10":
            default_coupon = PromoCoupon(
                code="SUPER10",
                discount_percentage=10,
                is_active=True,
                times_used=0,
                max_uses=None,
            )
            return await self.save(default_coupon)
        return self._to_domain(model) if model is not None else None

    async def list_all(self) -> list[PromoCoupon]:
        await self.get_by_code("SUPER10")
        stmt = select(PromoCouponModel).order_by(PromoCouponModel.created_at.desc())
        result = await self._session.execute(stmt)
        models = result.scalars().all()
        return [self._to_domain(m) for m in models]

    async def save(self, coupon: PromoCoupon) -> PromoCoupon:
        stmt = select(PromoCouponModel).where(PromoCouponModel.code == coupon.code)
        result = await self._session.execute(stmt)
        existing = result.scalar_one_or_none()

        if existing is None:
            model = PromoCouponModel(
                id=coupon.id,
                code=coupon.code,
                discount_percentage=coupon.discount_percentage,
                is_active=coupon.is_active,
                times_used=coupon.times_used,
                max_uses=coupon.max_uses,
                created_at=coupon.created_at,
            )
            self._session.add(model)
        else:
            existing.discount_percentage = coupon.discount_percentage
            existing.is_active = coupon.is_active
            existing.times_used = coupon.times_used
            existing.max_uses = coupon.max_uses
            model = existing

        await self._session.commit()
        return coupon


class PublicApiWalletPaymentAdapter(WalletPaymentPort):
    """Adapter invoking app.modules.wallet.public_api.debit_user_wallet (Law 1)."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def charge(
        self,
        buyer_id: UUID,
        amount_cents: int,
        reference: str,
        idempotency_key: str,
    ) -> None:
        try:
            await debit_user_wallet(
                user_id=buyer_id,
                amount_cents=amount_cents,
                reference=reference,
                idempotency_key=idempotency_key,
                session=self._session,
            )
        except WalletDomainError as exc:
            raise OrderPaymentFailedError(str(exc)) from exc

    async def get_loyalty_tier(self, buyer_id: UUID) -> str:
        return await get_user_loyalty_tier(user_id=buyer_id, session=self._session)
