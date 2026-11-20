"""FastAPI router for the Commerce bounded context (/api/v1/commerce)."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import PlainTextResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db_session
from app.core.event_bus import event_bus
from app.modules.commerce.application.dtos import (
    ApplyDynamicPricingCommand,
    CreateProductCommand,
    CreatePromoCouponCommand,
    OrderDTO,
    OrderItemInputDTO,
    PlaceOrderCommand,
    RestockProductCommand,
    ShipOrderCommand,
)
from app.modules.commerce.application.use_cases import (
    ApplyDynamicPricingUseCase,
    CreateProductUseCase,
    CreatePromoCouponUseCase,
    GenerateWeeklyExecutiveReportUseCase,
    GetCommerceFinancialSummaryUseCase,
    GetCrossSellBundleUseCase,
    GetOrderLifecycleMessagesUseCase,
    ListBuyerOrdersUseCase,
    ListCatalogUseCase,
    ListPromoCouponsUseCase,
    MarkOrderDeliveredUseCase,
    PlaceOrderUseCase,
    RestockProductUseCase,
    ShipOrderUseCase,
)
from app.modules.commerce.domain.exceptions import (
    DuplicateSkuError,
    EmptyOrderError,
    InsufficientStockError,
    InvalidOrderStateTransitionError,
    InvalidPromoCouponError,
    OrderNotFoundError,
    OrderPaymentFailedError,
    ProductNotFoundError,
)
from app.modules.commerce.infrastructure.repositories import (
    PublicApiWalletPaymentAdapter,
    SqlAlchemyOrderRepository,
    SqlAlchemyProductRepository,
    SqlAlchemyPromoCouponRepository,
)
from app.modules.commerce.presentation.schemas import (
    CommerceFinancialSummaryResponse,
    CreateProductRequest,
    CreatePromoCouponRequest,
    CrossSellBundleResponse,
    DynamicPricingRequest,
    DynamicPricingResponse,
    OrderItemResponse,
    OrderLifecycleMessagesResponse,
    OrderResponse,
    PlaceOrderRequest,
    ProductResponse,
    PromoCouponResponse,
    RestockProductRequest,
    ShipOrderRequest,
)
from app.modules.identity.public_api import UserPublicDTO, get_current_user

router = APIRouter(prefix="/api/v1/commerce", tags=["Commerce"])


def _to_order_response(order_dto: OrderDTO) -> OrderResponse:
    return OrderResponse(
        id=order_dto.id,
        buyer_id=order_dto.buyer_id,
        items=[OrderItemResponse.model_validate(i) for i in order_dto.items],
        total_cents=order_dto.total_cents,
        shipping_cost_cents=order_dto.shipping_cost_cents,
        total_cogs_cents=order_dto.total_cogs_cents,
        net_profit_cents=order_dto.net_profit_cents,
        currency=order_dto.currency,
        payment_method=order_dto.payment_method,
        status=order_dto.status,
        shipping_address=order_dto.shipping_address,
        idempotency_key=order_dto.idempotency_key,
        source_job_id=order_dto.source_job_id,
        carrier_name=order_dto.carrier_name,
        tracking_code=order_dto.tracking_code,
        coupon_code=order_dto.coupon_code,
        discount_cents=order_dto.discount_cents,
        whatsapp_checkout_url=order_dto.whatsapp_checkout_url,
        created_at=order_dto.created_at,
    )


@router.post(
    "/products",
    response_model=ProductResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_product(
    payload: CreateProductRequest,
    current_user: Annotated[UserPublicDTO, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> ProductResponse:
    """Creates a new product in the catalog associated with the authenticated merchant."""
    repository = SqlAlchemyProductRepository(session)
    use_case = CreateProductUseCase(
        product_repository=repository,
        event_bus=event_bus,
    )

    try:
        product_dto = await use_case.execute(
            CreateProductCommand(
                merchant_id=current_user.id,
                sku=payload.sku,
                title=payload.title,
                description=payload.description,
                price_cents=payload.price_cents,
                unit_cost_cents=payload.unit_cost_cents,
                stock_quantity=payload.stock_quantity,
                category_tag=payload.category_tag,
                complement_tags=tuple(payload.complement_tags),
            )
        )
    except DuplicateSkuError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc

    return ProductResponse.model_validate(product_dto)


@router.patch(
    "/products/{product_id}/stock",
    response_model=ProductResponse,
    status_code=status.HTTP_200_OK,
)
async def restock_product(
    product_id: UUID,
    payload: RestockProductRequest,
    _current_user: Annotated[UserPublicDTO, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> ProductResponse:
    """Adds positive stock units to an existing catalog product."""
    repository = SqlAlchemyProductRepository(session)
    use_case = RestockProductUseCase(product_repository=repository)

    try:
        product_dto = await use_case.execute(
            RestockProductCommand(
                product_id=product_id,
                quantity_to_add=payload.quantity_to_add,
            )
        )
    except ProductNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc

    return ProductResponse.model_validate(product_dto)


@router.post(
    "/products/{product_id}/dynamic-price",
    response_model=DynamicPricingResponse,
    status_code=status.HTTP_200_OK,
)
async def apply_dynamic_price(
    product_id: UUID,
    payload: DynamicPricingRequest,
    _current_user: Annotated[UserPublicDTO, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> DynamicPricingResponse:
    """Applies dynamic pricing based on stock scarcity and demand while protecting COGS margin."""
    repository = SqlAlchemyProductRepository(session)
    use_case = ApplyDynamicPricingUseCase(
        product_repository=repository,
        event_bus=event_bus,
    )

    try:
        result_dto = await use_case.execute(
            ApplyDynamicPricingCommand(
                product_id=product_id,
                demand_conversions=payload.demand_conversions,
            )
        )
    except ProductNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc

    return DynamicPricingResponse(
        product=ProductResponse.model_validate(result_dto.product),
        old_price_cents=result_dto.old_price_cents,
        new_price_cents=result_dto.new_price_cents,
        pricing_strategy=result_dto.pricing_strategy,
    )


@router.get(
    "/products",
    response_model=list[ProductResponse],
    status_code=status.HTTP_200_OK,
)
async def list_products(
    session: Annotated[AsyncSession, Depends(get_db_session)],
    search: str | None = None,
    category_tag: str | None = None,
) -> list[ProductResponse]:
    """Lists all active catalog products with available inventory, with optional search and category filters."""
    repository = SqlAlchemyProductRepository(session)
    use_case = ListCatalogUseCase(product_repository=repository)
    products = await use_case.execute(search=search, category_tag=category_tag)
    return [ProductResponse.model_validate(p) for p in products]



@router.get(
    "/products/{product_id}/cross-sell",
    response_model=CrossSellBundleResponse | None,
    status_code=status.HTTP_200_OK,
)
async def get_cross_sell_bundle(
    product_id: UUID,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> CrossSellBundleResponse | None:
    """Calculates and returns a smart AI cross-sell bundle recommendation protecting COGS floor."""
    repository = SqlAlchemyProductRepository(session)
    use_case = GetCrossSellBundleUseCase(product_repository=repository)
    bundle_dto = await use_case.execute(product_id=product_id)
    if bundle_dto is None:
        return None
    return CrossSellBundleResponse.model_validate(bundle_dto)


@router.post(
    "/coupons",
    response_model=PromoCouponResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_promo_coupon(
    payload: CreatePromoCouponRequest,
    _current_user: Annotated[UserPublicDTO, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> PromoCouponResponse:
    """Creates or updates a promotional coupon (e.g. SUPER10) protected by the 1.15x COGS floor."""
    coupon_repo = SqlAlchemyPromoCouponRepository(session)
    use_case = CreatePromoCouponUseCase(coupon_repository=coupon_repo)
    coupon_dto = await use_case.execute(
        CreatePromoCouponCommand(
            code=payload.code,
            discount_percentage=payload.discount_percentage,
            max_uses=payload.max_uses,
        )
    )
    return PromoCouponResponse.model_validate(coupon_dto)


@router.get(
    "/coupons",
    response_model=list[PromoCouponResponse],
    status_code=status.HTTP_200_OK,
)
async def list_promo_coupons(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> list[PromoCouponResponse]:
    """Lists active promotional coupons available in the store."""
    coupon_repo = SqlAlchemyPromoCouponRepository(session)
    use_case = ListPromoCouponsUseCase(coupon_repository=coupon_repo)
    coupons = await use_case.execute()
    return [PromoCouponResponse.model_validate(c) for c in coupons]


@router.post(
    "/orders",
    response_model=OrderResponse,
    status_code=status.HTTP_201_CREATED,
)
async def place_order(
    payload: PlaceOrderRequest,
    current_user: Annotated[UserPublicDTO, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> OrderResponse:
    """Places a new order using WALLET or CASH_ON_DELIVERY with optional video attribution and promo coupon."""
    product_repo = SqlAlchemyProductRepository(session)
    order_repo = SqlAlchemyOrderRepository(session)
    coupon_repo = SqlAlchemyPromoCouponRepository(session)
    wallet_adapter = PublicApiWalletPaymentAdapter(session)
    use_case = PlaceOrderUseCase(
        product_repository=product_repo,
        order_repository=order_repo,
        wallet_payment_port=wallet_adapter,
        event_bus=event_bus,
        coupon_repository=coupon_repo,
    )

    try:
        order_dto = await use_case.execute(
            PlaceOrderCommand(
                buyer_id=current_user.id,
                items=tuple(
                    OrderItemInputDTO(
                        product_id=item.product_id,
                        quantity=item.quantity,
                        variant_sku=item.variant_sku,
                    )
                    for item in payload.items
                ),
                payment_method=payload.payment_method,
                shipping_address=payload.shipping_address,
                idempotency_key=payload.idempotency_key,
                shipping_cost_cents=payload.shipping_cost_cents,
                source_job_id=payload.source_job_id,
                coupon_code=payload.coupon_code,
            )
        )
    except ProductNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except (
        InsufficientStockError,
        OrderPaymentFailedError,
        EmptyOrderError,
        InvalidPromoCouponError,
    ) as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

    return _to_order_response(order_dto)


@router.post(
    "/orders/{order_id}/ship",
    response_model=OrderResponse,
    status_code=status.HTTP_200_OK,
)
async def ship_order(
    order_id: UUID,
    payload: ShipOrderRequest,
    _current_user: Annotated[UserPublicDTO, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> OrderResponse:
    """Marks a CONFIRMED order as SHIPPED with carrier & tracking guide and emits OrderShippedEvent."""
    order_repo = SqlAlchemyOrderRepository(session)
    use_case = ShipOrderUseCase(
        order_repository=order_repo,
        event_bus=event_bus,
    )

    try:
        order_dto = await use_case.execute(
            ShipOrderCommand(
                order_id=order_id,
                carrier_name=payload.carrier_name,
                tracking_code=payload.tracking_code,
            )
        )
    except OrderNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except InvalidOrderStateTransitionError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc

    return _to_order_response(order_dto)


@router.get(
    "/orders/{order_id}/messages",
    response_model=OrderLifecycleMessagesResponse,
    status_code=status.HTTP_200_OK,
)
async def get_order_lifecycle_messages(
    order_id: UUID,
    _current_user: Annotated[UserPublicDTO, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> OrderLifecycleMessagesResponse:
    """Returns the 3 automated post-sale customer messages (Confirmation, Shipping, Post-Delivery) and wa.me links."""
    order_repo = SqlAlchemyOrderRepository(session)
    use_case = GetOrderLifecycleMessagesUseCase(order_repository=order_repo)

    try:
        messages_dto = await use_case.execute(order_id=order_id)
    except OrderNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc

    return OrderLifecycleMessagesResponse.model_validate(messages_dto)


@router.post(
    "/orders/{order_id}/deliver",
    response_model=OrderResponse,
    status_code=status.HTTP_200_OK,
)
async def deliver_order(
    order_id: UUID,
    current_user: Annotated[UserPublicDTO, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> OrderResponse:
    """Marks an order as DELIVERED and emits OrderDeliveredAndSettledEvent for Wallet settlement."""
    order_repo = SqlAlchemyOrderRepository(session)
    product_repo = SqlAlchemyProductRepository(session)
    use_case = MarkOrderDeliveredUseCase(
        order_repository=order_repo,
        product_repository=product_repo,
        event_bus=event_bus,
    )

    try:
        order_dto = await use_case.execute(
            order_id=order_id,
            acting_user_id=current_user.id,
        )
    except OrderNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except InvalidOrderStateTransitionError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc

    return _to_order_response(order_dto)


@router.get(
    "/orders/me",
    response_model=list[OrderResponse],
    status_code=status.HTTP_200_OK,
)
async def list_my_orders(
    current_user: Annotated[UserPublicDTO, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> list[OrderResponse]:
    """Returns the authenticated buyer's purchase order history."""
    order_repo = SqlAlchemyOrderRepository(session)
    use_case = ListBuyerOrdersUseCase(order_repository=order_repo)
    orders = await use_case.execute(buyer_id=current_user.id)
    return [_to_order_response(o) for o in orders]


@router.get(
    "/analytics/summary",
    response_model=CommerceFinancialSummaryResponse,
    status_code=status.HTTP_200_OK,
)
async def get_commerce_analytics_summary(
    current_user: Annotated[UserPublicDTO, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> CommerceFinancialSummaryResponse:
    """Returns real-time inventory valuation, COGS, shipping costs, and realized net profit."""
    product_repo = SqlAlchemyProductRepository(session)
    order_repo = SqlAlchemyOrderRepository(session)
    use_case = GetCommerceFinancialSummaryUseCase(
        product_repository=product_repo,
        order_repository=order_repo,
    )
    summary = await use_case.execute(user_id=current_user.id)
    return CommerceFinancialSummaryResponse.model_validate(summary)


@router.get(
    "/analytics/weekly-report",
    response_class=PlainTextResponse,
    status_code=status.HTTP_200_OK,
)
async def download_weekly_executive_report(
    current_user: Annotated[UserPublicDTO, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> PlainTextResponse:
    """Generates and downloads the weekly executive Markdown report with unit economics & pricing."""
    product_repo = SqlAlchemyProductRepository(session)
    order_repo = SqlAlchemyOrderRepository(session)
    use_case = GenerateWeeklyExecutiveReportUseCase(
        product_repository=product_repo,
        order_repository=order_repo,
    )
    report_md = await use_case.execute(user_id=current_user.id)
    return PlainTextResponse(
        content=report_md,
        media_type="text/markdown",
        headers={
            "Content-Disposition": 'attachment; filename="weekly_executive_report.md"'
        },
    )
