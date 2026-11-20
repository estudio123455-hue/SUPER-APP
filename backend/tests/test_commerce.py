"""Unit and integration tests for Commerce, Unit Economics, COD Settlement, and Dynamic Pricing."""

from collections.abc import AsyncGenerator
from uuid import UUID, uuid4

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import StaticPool

from app.core.database import (
    SQLITE_SCHEMA_TRANSLATE_MAP,
    get_db_session,
    reset_session_factory,
    set_session_factory,
)
from app.core.event_bus import event_bus
from app.main import app
from app.modules.commerce.domain.entities import Product
from app.modules.commerce.domain.exceptions import InsufficientStockError
from app.modules.commerce.infrastructure.models import (
    CommerceBase,
    OrderItemModel,
    OrderModel,
    ProductModel,
)
from app.modules.identity.infrastructure.models import IdentityBase
from app.modules.wallet.application.handlers import register_wallet_event_handlers
from app.modules.wallet.infrastructure.models import WalletBase


@pytest.fixture
async def sqlite_engine() -> AsyncGenerator[AsyncEngine, None]:
    """Creates a shared in-memory SQLite engine for identity, wallet, and commerce schemas."""
    base_engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        execution_options={"schema_translate_map": SQLITE_SCHEMA_TRANSLATE_MAP},
    )
    async with base_engine.begin() as conn:
        await conn.run_sync(IdentityBase.metadata.create_all)
        await conn.run_sync(WalletBase.metadata.create_all)
        await conn.run_sync(CommerceBase.metadata.create_all)
    yield base_engine
    await base_engine.dispose()


@pytest.fixture
async def async_client(sqlite_engine: AsyncEngine) -> AsyncGenerator[AsyncClient, None]:
    """Configures test session factory, registers EventBus handlers, and yields client."""
    session_factory = async_sessionmaker(
        bind=sqlite_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )
    set_session_factory(session_factory)

    async def _override_get_db() -> AsyncGenerator[AsyncSession, None]:
        async with session_factory() as session:
            yield session

    app.dependency_overrides[get_db_session] = _override_get_db
    event_bus.clear()
    register_wallet_event_handlers(event_bus)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        yield client

    app.dependency_overrides.clear()
    event_bus.clear()
    reset_session_factory()


def test_commerce_domain_invariants_and_schema_isolation() -> None:
    """Verifies Product stock reservation/release rules, COGS margin, and Law 2 schema isolation."""
    assert ProductModel.__table__.schema == "commerce_schema"
    assert OrderModel.__table__.schema == "commerce_schema"
    assert OrderItemModel.__table__.schema == "commerce_schema"
    assert len(ProductModel.__table__.foreign_keys) == 0
    assert len(OrderModel.__table__.foreign_keys) == 0
    assert len(OrderItemModel.__table__.foreign_keys) == 0

    product = Product(
        merchant_id=uuid4(),
        sku="  ergo-stand-pro ",
        title="Soporte Ergonómico Pro",
        description="Soporte de aluminio ajustable",
        price_cents=9_500_000,
        unit_cost_cents=4_200_000,
        stock_quantity=5,
    )
    assert product.sku == "ERGO-STAND-PRO"
    assert product.unit_margin_cents == 5_300_000
    assert product.margin_percentage == pytest.approx(55.79, rel=1e-2)

    reserved = product.reserve_stock(2)
    assert reserved.stock_quantity == 3

    released = reserved.release_stock(2)
    assert released.stock_quantity == 5

    with pytest.raises(InsufficientStockError):
        product.reserve_stock(10)


async def test_commerce_end_to_end_catalog_wallet_and_cod_orders(
    async_client: AsyncClient,
) -> None:
    """Tests product creation, restock, WALLET checkout, rollback, COD checkout, and WhatsApp link."""
    await async_client.post(
        "/api/v1/identity/register",
        json={
            "email": "shopper@superapp.io",
            "password": "ShopperPassword123!",
            "full_name": "Jeff Buyer",
            "roles": ["USER", "MERCHANT"],
        },
    )
    login_res = await async_client.post(
        "/api/v1/identity/login",
        json={
            "email": "shopper@superapp.io",
            "password": "ShopperPassword123!",
        },
    )
    headers = {"Authorization": f"Bearer {login_res.json()['access_token']}"}

    # 1. Create product ($95,000 COP -> 9_500_000 cents, stock = 10)
    prod_res = await async_client.post(
        "/api/v1/commerce/products",
        json={
            "sku": "ERGO-COMBO-95K",
            "title": "Combo Soporte Ergonómico + Hub",
            "description": "Kit ergonómico de escritorio",
            "price_cents": 9_500_000,
            "stock_quantity": 10,
        },
        headers=headers,
    )
    assert prod_res.status_code == 201
    product_id = prod_res.json()["id"]

    # 1b. Restock product (+5 units -> stock becomes 15)
    restock_res = await async_client.patch(
        f"/api/v1/commerce/products/{product_id}/stock",
        json={"quantity_to_add": 5},
        headers=headers,
    )
    assert restock_res.status_code == 200
    assert restock_res.json()["stock_quantity"] == 15

    catalog_res = await async_client.get("/api/v1/commerce/products")
    assert catalog_res.status_code == 200
    catalog = catalog_res.json()
    assert len(catalog) == 1
    assert catalog[0]["sku"] == "ERGO-COMBO-95K"
    assert catalog[0]["stock_quantity"] == 15

    # 2. Successful WALLET purchase (top-up 200,000 COP = 20_000_000 cents, buy 2 units = 19_000_000 cents)
    dep_res = await async_client.post(
        "/api/v1/wallet/me/deposit",
        json={
            "amount_cents": 20_000_000,
            "reference": "Top-up for shopping",
            "idempotency_key": "shop-topup-001",
        },
        headers=headers,
    )
    assert dep_res.status_code == 201

    wallet_order_res = await async_client.post(
        "/api/v1/commerce/orders",
        json={
            "items": [{"product_id": product_id, "quantity": 2}],
            "payment_method": "WALLET",
            "shipping_address": "Carrera 7 #71-21, Bogotá",
            "idempotency_key": "order-wallet-001",
        },
        headers=headers,
    )
    assert wallet_order_res.status_code == 201
    wallet_order = wallet_order_res.json()
    assert wallet_order["status"] == "CONFIRMED"
    assert wallet_order["total_cents"] == 19_000_000
    assert wallet_order["payment_method"] == "WALLET"
    assert wallet_order["whatsapp_checkout_url"].startswith("https://wa.me/")
    assert "BILLETERA" in wallet_order["whatsapp_checkout_url"]

    # Verify stock decreased from 15 to 13, and wallet balance decreased from 20_000_000 to 1_000_000
    cat_after_wallet = (await async_client.get("/api/v1/commerce/products")).json()
    assert cat_after_wallet[0]["stock_quantity"] == 13

    wallet_after = (
        await async_client.get("/api/v1/wallet/me", headers=headers)
    ).json()
    assert wallet_after["wallet"]["balance_cents"] == 1_000_000

    # 3. Failed WALLET purchase due to insufficient funds (1_000_000 cents < 9_500_000 needed)
    failed_order_res = await async_client.post(
        "/api/v1/commerce/orders",
        json={
            "items": [{"product_id": product_id, "quantity": 1}],
            "payment_method": "WALLET",
            "shipping_address": "Carrera 7 #71-21, Bogotá",
            "idempotency_key": "order-wallet-fail-002",
        },
        headers=headers,
    )
    assert failed_order_res.status_code == 400
    assert "Insufficient funds" in failed_order_res.json()["detail"]

    # Verify stock was rolled back and remains 13!
    cat_after_fail = (await async_client.get("/api/v1/commerce/products")).json()
    assert cat_after_fail[0]["stock_quantity"] == 13

    # 4. Successful CASH_ON_DELIVERY purchase (3 units -> stock drops from 13 to 10, wallet stays at 1_000_000)
    cod_order_res = await async_client.post(
        "/api/v1/commerce/orders",
        json={
            "items": [{"product_id": product_id, "quantity": 3}],
            "payment_method": "CASH_ON_DELIVERY",
            "shipping_address": "Av. El Poblado #10-50, Medellín",
            "idempotency_key": "order-cod-003",
        },
        headers=headers,
    )
    assert cod_order_res.status_code == 201
    cod_order = cod_order_res.json()
    assert cod_order["status"] == "CONFIRMED"
    assert cod_order["payment_method"] == "CASH_ON_DELIVERY"
    assert cod_order["total_cents"] == 28_500_000
    assert "CONTRAENTREGA" in cod_order["whatsapp_checkout_url"]

    cat_after_cod = (await async_client.get("/api/v1/commerce/products")).json()
    assert cat_after_cod[0]["stock_quantity"] == 10

    my_orders = (
        await async_client.get("/api/v1/commerce/orders/me", headers=headers)
    ).json()
    assert len(my_orders) == 2


async def test_unit_economics_cod_delivery_and_wallet_settlement(
    async_client: AsyncClient,
) -> None:
    """Verifies COGS, shipping cost, net profit calculation, COD delivery, and reactive Wallet settlement."""
    await async_client.post(
        "/api/v1/identity/register",
        json={
            "email": "founder@superapp.io",
            "password": "FounderPassword123!",
            "full_name": "Founder Merchant",
            "roles": ["USER", "MERCHANT"],
        },
    )
    login_res = await async_client.post(
        "/api/v1/identity/login",
        json={
            "email": "founder@superapp.io",
            "password": "FounderPassword123!",
        },
    )
    headers = {"Authorization": f"Bearer {login_res.json()['access_token']}"}

    # 1. Create product: Selling Price $95,000 COP (9_500_000), COGS $42,000 COP (4_200_000), Stock 10
    prod_res = await async_client.post(
        "/api/v1/commerce/products",
        json={
            "sku": "COMBO-ERGO-COGS",
            "title": "Combo Setup Ergonómico: Lámpara Monitor + Soporte Laptop",
            "description": "Kit con unidad económica real",
            "price_cents": 9_500_000,
            "unit_cost_cents": 4_200_000,
            "stock_quantity": 10,
        },
        headers=headers,
    )
    assert prod_res.status_code == 201
    prod_data = prod_res.json()
    product_id = prod_data["id"]
    assert prod_data["unit_margin_cents"] == 5_300_000

    # 2. Place a CASH_ON_DELIVERY order of 2 units ($190,000 gross, $84,000 COGS, $12,000 shipping -> $94,000 net profit)
    order_res = await async_client.post(
        "/api/v1/commerce/orders",
        json={
            "items": [{"product_id": product_id, "quantity": 2}],
            "payment_method": "CASH_ON_DELIVERY",
            "shipping_address": "Calle 93 #11-27, Bogotá",
            "shipping_cost_cents": 1_200_000,
            "idempotency_key": "cod-unit-econ-001",
        },
        headers=headers,
    )
    assert order_res.status_code == 201
    order_data = order_res.json()
    order_id = order_data["id"]
    assert order_data["total_cents"] == 19_000_000
    assert order_data["total_cogs_cents"] == 8_400_000
    assert order_data["shipping_cost_cents"] == 1_200_000
    assert order_data["net_profit_cents"] == 9_400_000

    # Wallet starts at 0 before COD delivery
    wallet_before = (
        await async_client.get("/api/v1/wallet/me", headers=headers)
    ).json()
    assert wallet_before["wallet"]["balance_cents"] == 0

    # 3. Mark COD order as DELIVERED -> reactive handler credits net profit ($94,000 COP = 9_400_000 cents) to Wallet!
    deliver_res = await async_client.post(
        f"/api/v1/commerce/orders/{order_id}/deliver",
        headers=headers,
    )
    assert deliver_res.status_code == 200
    assert deliver_res.json()["status"] == "DELIVERED"

    # Attempting to deliver an already DELIVERED order must return 409 Conflict
    dup_deliver = await async_client.post(
        f"/api/v1/commerce/orders/{order_id}/deliver",
        headers=headers,
    )
    assert dup_deliver.status_code == 409

    wallet_after = (
        await async_client.get("/api/v1/wallet/me", headers=headers)
    ).json()
    assert wallet_after["wallet"]["balance_cents"] == 9_400_000
    assert any(
        e["idempotency_key"] == f"settlement-{order_id}"
        for e in wallet_after["recent_entries"]
    )

    # 4. Verify GET /api/v1/commerce/analytics/summary
    summary_res = await async_client.get(
        "/api/v1/commerce/analytics/summary",
        headers=headers,
    )
    assert summary_res.status_code == 200
    summary = summary_res.json()
    assert summary["inventory_cost_value_cents"] == 33_600_000
    assert summary["inventory_retail_value_cents"] == 76_000_000
    assert summary["delivered_orders_count"] == 1
    assert summary["realized_net_profit_cents"] == 9_400_000


async def test_dynamic_pricing_surge_discount_and_cogs_floor(
    async_client: AsyncClient,
) -> None:
    """Verifies dynamic pricing rules (+10% surge, -8% discount, and strict 1.25x COGS floor)."""
    # Pure domain floor check: if price is close to 1.25 * COGS, discount never pierces the floor
    tight_margin_product = Product(
        merchant_id=uuid4(),
        sku="FLOOR-TEST",
        title="Producto Margen Ajustado",
        description="Test de piso de margen",
        price_cents=10_200_000,  # $102,000 COP
        unit_cost_cents=8_000_000,  # COGS $80,000 COP -> 1.25x floor = $100,000 COP (10_000_000)
        stock_quantity=20,
    )
    discounted_prod, strategy = tight_margin_product.apply_dynamic_pricing(
        demand_conversions=0
    )
    assert strategy == "FLASH_ROTATION_DISCOUNT"
    # -8% of 10_200_000 would be 9_384_000, but floor clamps it to 10_000_000!
    assert discounted_prod.price_cents == 10_000_000

    # Integration test via API
    await async_client.post(
        "/api/v1/identity/register",
        json={
            "email": "pricing_ai@superapp.io",
            "password": "PricingPassword123!",
            "full_name": "Dynamic Pricer",
            "roles": ["MERCHANT"],
        },
    )
    login_res = await async_client.post(
        "/api/v1/identity/login",
        json={
            "email": "pricing_ai@superapp.io",
            "password": "PricingPassword123!",
        },
    )
    headers = {"Authorization": f"Bearer {login_res.json()['access_token']}"}

    prod_res = await async_client.post(
        "/api/v1/commerce/products",
        json={
            "sku": "RBR-JACKET-DYN",
            "title": "Chaqueta Oversize RBR Edition",
            "description": "Edición limitada",
            "price_cents": 18_000_000,
            "unit_cost_cents": 7_500_000,
            "stock_quantity": 2,  # Low stock (<= 3) triggers SURGE_HIGH_DEMAND (+10%)
        },
        headers=headers,
    )
    product_id = prod_res.json()["id"]

    dyn_res = await async_client.post(
        f"/api/v1/commerce/products/{product_id}/dynamic-price",
        json={"demand_conversions": 1},
        headers=headers,
    )
    assert dyn_res.status_code == 200
    dyn_data = dyn_res.json()
    assert dyn_data["pricing_strategy"] == "SURGE_HIGH_DEMAND"
    assert dyn_data["old_price_cents"] == 18_000_000
    assert dyn_data["new_price_cents"] == 19_800_000


async def test_weekly_executive_report_download(
    async_client: AsyncClient,
) -> None:
    """Verifies GET /api/v1/commerce/analytics/weekly-report generates a complete Markdown executive report."""
    await async_client.post(
        "/api/v1/identity/register",
        json={
            "email": "ceo@superapp.io",
            "password": "CeoPassword123!",
            "full_name": "Executive Merchant",
            "roles": ["USER", "MERCHANT"],
        },
    )
    login_res = await async_client.post(
        "/api/v1/identity/login",
        json={
            "email": "ceo@superapp.io",
            "password": "CeoPassword123!",
        },
    )
    headers = {"Authorization": f"Bearer {login_res.json()['access_token']}"}

    prod_res = await async_client.post(
        "/api/v1/commerce/products",
        json={
            "sku": "COMBO-ERGO-EXEC",
            "title": "Combo Setup Ergonómico: Lámpara Monitor + Soporte Laptop",
            "description": "Combo ejecutivo",
            "price_cents": 9_500_000,
            "unit_cost_cents": 4_200_000,
            "stock_quantity": 10,
        },
        headers=headers,
    )
    product_id = prod_res.json()["id"]

    await async_client.post(
        "/api/v1/commerce/orders",
        json={
            "items": [{"product_id": product_id, "quantity": 1}],
            "payment_method": "CASH_ON_DELIVERY",
            "shipping_address": "Calle 93 #11-27, Bogotá",
            "shipping_cost_cents": 1_200_000,
            "idempotency_key": "exec-report-order-001",
        },
        headers=headers,
    )

    report_res = await async_client.get(
        "/api/v1/commerce/analytics/weekly-report",
        headers=headers,
    )
    assert report_res.status_code == 200
    assert "text/markdown" in report_res.headers.get("content-type", "")
    assert 'filename="weekly_executive_report.md"' in report_res.headers.get(
        "content-disposition", ""
    )
    assert "Reporte Ejecutivo Semanal" in report_res.text
    assert "COMBO-ERGO-EXEC" in report_res.text
    assert "Resumen de Unidad Económica (COP)" in report_res.text


async def test_order_shipping_tracking_and_lifecycle_messages(
    async_client: AsyncClient,
) -> None:
    """Verifies CONFIRMED -> SHIPPED -> DELIVERED lifecycle, tracking code, and 3 automated customer messages."""
    await async_client.post(
        "/api/v1/identity/register",
        json={
            "email": "logistics@superapp.io",
            "password": "LogisticsPassword123!",
            "full_name": "Logistics Manager",
            "roles": ["USER", "MERCHANT"],
        },
    )
    login_res = await async_client.post(
        "/api/v1/identity/login",
        json={
            "email": "logistics@superapp.io",
            "password": "LogisticsPassword123!",
        },
    )
    headers = {"Authorization": f"Bearer {login_res.json()['access_token']}"}

    prod_res = await async_client.post(
        "/api/v1/commerce/products",
        json={
            "sku": "RBR-HOODIE-SHIP",
            "title": "Hoodie Heavyweight RBR Edition",
            "description": "Algodón peruano 400g",
            "price_cents": 15_000_000,
            "unit_cost_cents": 6_000_000,
            "stock_quantity": 8,
        },
        headers=headers,
    )
    assert prod_res.status_code == 201
    product_id = prod_res.json()["id"]

    # 1. Place order (starts in CONFIRMED)
    order_res = await async_client.post(
        "/api/v1/commerce/orders",
        json={
            "items": [{"product_id": product_id, "quantity": 1}],
            "payment_method": "CASH_ON_DELIVERY",
            "shipping_address": "Carrera 15 #85-30, Bogotá, Colombia",
            "shipping_cost_cents": 1_200_000,
            "idempotency_key": "ship-lifecycle-order-001",
        },
        headers=headers,
    )
    assert order_res.status_code == 201
    order_data = order_res.json()
    order_id = order_data["id"]
    assert order_data["status"] == "CONFIRMED"
    assert order_data["carrier_name"] is None
    assert order_data["tracking_code"] is None

    # 2. Ship order with carrier & tracking guide (CONFIRMED -> SHIPPED)
    ship_res = await async_client.post(
        f"/api/v1/commerce/orders/{order_id}/ship",
        json={
            "carrier_name": "InterRapidísimo",
            "tracking_code": "GUIA-2400991188",
        },
        headers=headers,
    )
    assert ship_res.status_code == 200
    shipped_data = ship_res.json()
    assert shipped_data["status"] == "SHIPPED"
    assert shipped_data["carrier_name"] == "InterRapidísimo"
    assert shipped_data["tracking_code"] == "GUIA-2400991188"

    # Attempting to ship an already SHIPPED order must return 409 Conflict
    dup_ship = await async_client.post(
        f"/api/v1/commerce/orders/{order_id}/ship",
        json={
            "carrier_name": "Servientrega",
            "tracking_code": "GUIA-999999",
        },
        headers=headers,
    )
    assert dup_ship.status_code == 409

    # 3. Verify GET /api/v1/commerce/orders/{order_id}/messages returns all 3 messages + wa.me links
    msgs_res = await async_client.get(
        f"/api/v1/commerce/orders/{order_id}/messages",
        headers=headers,
    )
    assert msgs_res.status_code == 200
    msgs = msgs_res.json()
    assert msgs["order_id"] == order_id
    assert msgs["status"] == "SHIPPED"
    assert "Hoodie Heavyweight RBR Edition" in msgs["confirmation_msg"]
    assert "Pago Contraentrega (COD)" in msgs["confirmation_msg"]
    assert "InterRapidísimo" in msgs["shipping_msg"]
    assert "GUIA-2400991188" in msgs["shipping_msg"]
    assert "efectivo exacto" in msgs["shipping_msg"]
    assert "SUPER10" in msgs["post_delivery_msg"]
    assert msgs["confirmation_whatsapp_url"].startswith("https://wa.me/")
    assert msgs["shipping_whatsapp_url"].startswith("https://wa.me/")
    assert msgs["post_delivery_whatsapp_url"].startswith("https://wa.me/")

    # 4. Complete delivery (SHIPPED -> DELIVERED) and verify Wallet settlement
    deliver_res = await async_client.post(
        f"/api/v1/commerce/orders/{order_id}/deliver",
        headers=headers,
    )
    assert deliver_res.status_code == 200
    assert deliver_res.json()["status"] == "DELIVERED"


async def test_promo_coupon_super10_discount_and_cogs_protection(
    async_client: AsyncClient,
) -> None:
    """Verifies SUPER10 10% discount, rejection of invalid coupons, and 1.15x COGS floor protection."""
    await async_client.post(
        "/api/v1/identity/register",
        json={
            "email": "coupons@superapp.io",
            "password": "CouponPassword123!",
            "full_name": "Coupon Tester",
            "roles": ["USER", "MERCHANT"],
        },
    )
    login_res = await async_client.post(
        "/api/v1/identity/login",
        json={
            "email": "coupons@superapp.io",
            "password": "CouponPassword123!",
        },
    )
    headers = {"Authorization": f"Bearer {login_res.json()['access_token']}"}

    # 1. Product with healthy margin: Price $100,000 COP, COGS $40,000 COP
    prod_healthy = (
        await async_client.post(
            "/api/v1/commerce/products",
            json={
                "sku": "ERGO-COUPON-01",
                "title": "Lámpara Monitor Pro",
                "description": "Saludable para cupón SUPER10",
                "price_cents": 10_000_000,
                "unit_cost_cents": 4_000_000,
                "stock_quantity": 10,
            },
            headers=headers,
        )
    ).json()

    # Apply SUPER10 (10% OFF -> $10,000 COP discount -> final total $90,000 COP)
    order_super10 = await async_client.post(
        "/api/v1/commerce/orders",
        json={
            "items": [{"product_id": prod_healthy["id"], "quantity": 1}],
            "payment_method": "CASH_ON_DELIVERY",
            "shipping_address": "Calle 93 #11-27, Bogotá",
            "shipping_cost_cents": 1_000_000,
            "idempotency_key": "coupon-super10-order-01",
            "coupon_code": "super10",
        },
        headers=headers,
    )
    assert order_super10.status_code == 201
    o1 = order_super10.json()
    assert o1["coupon_code"] == "SUPER10"
    assert o1["discount_cents"] == 1_000_000
    assert o1["total_cents"] == 9_000_000
    # Net profit = $90,000 - $40,000 COGS - $10,000 shipping = $40,000 COP (4_000_000 cents)
    assert o1["net_profit_cents"] == 4_000_000

    # 2. Invalid coupon code must be rejected with 400 Bad Request and stock rolled back
    invalid_order = await async_client.post(
        "/api/v1/commerce/orders",
        json={
            "items": [{"product_id": prod_healthy["id"], "quantity": 1}],
            "payment_method": "CASH_ON_DELIVERY",
            "shipping_address": "Calle 93 #11-27, Bogotá",
            "idempotency_key": "coupon-invalid-order-02",
            "coupon_code": "NOEXISTE99",
        },
        headers=headers,
    )
    assert invalid_order.status_code == 400
    assert "NOEXISTE99" in invalid_order.json()["detail"]

    # 3. Create a custom 30% coupon via POST /api/v1/commerce/coupons and verify 1.15x COGS floor protection!
    coupon_res = await async_client.post(
        "/api/v1/commerce/coupons",
        json={
            "code": "FLASH30",
            "discount_percentage": 30,
            "max_uses": 5,
        },
        headers=headers,
    )
    assert coupon_res.status_code == 201
    assert coupon_res.json()["code"] == "FLASH30"

    # Product where COGS is $80,000 COP (1.15x floor = $92,000 COP) and selling price is $100,000 COP
    prod_tight = (
        await async_client.post(
            "/api/v1/commerce/products",
            json={
                "sku": "TIGHT-COGS-COUPON",
                "title": "Monitor Brazo Hidráulico",
                "description": "Protección de piso COGS 1.15x",
                "price_cents": 10_000_000,  # $100,000 COP
                "unit_cost_cents": 8_000_000,  # COGS $80,000 COP -> 1.15x floor = $92,000 COP (9_200_000)
                "stock_quantity": 5,
            },
            headers=headers,
        )
    ).json()

    # 30% discount would be $30,000 COP (dropping price to $70,000 < COGS!),
    # so COGS protection clamps discount to $8,000 COP (final price $92,000 COP = 1.15x COGS)
    protected_order = await async_client.post(
        "/api/v1/commerce/orders",
        json={
            "items": [{"product_id": prod_tight["id"], "quantity": 1}],
            "payment_method": "CASH_ON_DELIVERY",
            "shipping_address": "Calle 93 #11-27, Bogotá",
            "idempotency_key": "coupon-cogs-protected-order-03",
            "coupon_code": "FLASH30",
        },
        headers=headers,
    )
    assert protected_order.status_code == 201
    o3 = protected_order.json()
    assert o3["coupon_code"] == "FLASH30"
    assert o3["discount_cents"] == 800_000
    assert o3["total_cents"] == 9_200_000


async def test_product_variants_size_stock_isolation(
    async_client: AsyncClient,
) -> None:
    """Verifies variant value object (size, color, stock) and isolated stock reservation."""
    from uuid import uuid4
    from app.core.database import get_session_factory
    from app.modules.commerce.domain.entities import Product, ProductVariant
    from app.modules.commerce.domain.exceptions import InsufficientStockError
    from app.modules.commerce.infrastructure.repositories import (
        SqlAlchemyProductRepository,
    )

    # 1. Pure Domain Verification (Law 3)
    v_m = ProductVariant(
        variant_sku="RBR-JKT-M-BLK",
        size="M",
        color="Negro",
        stock_quantity=4,
    )
    v_l = ProductVariant(
        variant_sku="RBR-JKT-L-BLK",
        size="L",
        color="Negro",
        stock_quantity=3,
    )
    merchant_id = uuid4()
    product = Product(
        merchant_id=merchant_id,
        sku="CHAQUETA-RBR-EDITION",
        title="Chaqueta Oversize RBR Edition",
        description="Chaqueta streetwear con variantes de talla",
        price_cents=18_000_000,
        unit_cost_cents=7_500_000,
        stock_quantity=7,
        variants=(v_m, v_l),
    )

    # Reserve 2 units of Size M
    p_reserved = product.reserve_stock(2, variant_sku="RBR-JKT-M-BLK")
    assert p_reserved.stock_quantity == 5
    assert p_reserved.variants[0].stock_quantity == 2
    assert p_reserved.variants[1].stock_quantity == 3  # Size L untouched!

    # Exhaust remaining Size M: attempting 3 units fails with InsufficientStockError
    with pytest.raises(InsufficientStockError) as exc_info:
        p_reserved.reserve_stock(3, variant_sku="RBR-JKT-M-BLK")
    assert "RBR-JKT-M-BLK" in str(exc_info.value)

    # 2. Integration via API & SqlAlchemy Persistence
    await async_client.post(
        "/api/v1/identity/register",
        json={
            "email": "variants_merchant@superapp.io",
            "password": "VariantsPassword123!",
            "full_name": "Variants Merchant",
            "roles": ["USER", "MERCHANT"],
        },
    )
    login_res = await async_client.post(
        "/api/v1/identity/login",
        json={
            "email": "variants_merchant@superapp.io",
            "password": "VariantsPassword123!",
        },
    )
    headers = {"Authorization": f"Bearer {login_res.json()['access_token']}"}

    session_factory = get_session_factory()
    async with session_factory() as session:
        repo = SqlAlchemyProductRepository(session)
        saved_prod = await repo.save(product)
        prod_id = saved_prod.id

    # Place order for 2 units of Size M
    res_order_m = await async_client.post(
        "/api/v1/commerce/orders",
        json={
            "items": [
                {
                    "product_id": str(prod_id),
                    "quantity": 2,
                    "variant_sku": "RBR-JKT-M-BLK",
                }
            ],
            "payment_method": "CASH_ON_DELIVERY",
            "shipping_address": "Carrera 7 #71-21, Bogotá",
            "idempotency_key": f"order-variant-m-{uuid4()}",
        },
        headers=headers,
    )
    assert res_order_m.status_code == 201
    order_data = res_order_m.json()
    assert order_data["items"][0]["variant_sku"] == "RBR-JKT-M-BLK"

    # Verify inventory state via GET /api/v1/commerce/products
    cat_res = await async_client.get("/api/v1/commerce/products")
    assert cat_res.status_code == 200
    prod_in_catalog = next(p for p in cat_res.json() if p["id"] == str(prod_id))
    assert prod_in_catalog["stock_quantity"] == 5
    variant_m = next(
        v for v in prod_in_catalog["variants"] if v["variant_sku"] == "RBR-JKT-M-BLK"
    )
    variant_l = next(
        v for v in prod_in_catalog["variants"] if v["variant_sku"] == "RBR-JKT-L-BLK"
    )
    assert variant_m["stock_quantity"] == 2
    assert variant_l["stock_quantity"] == 3

    # Attempt to order 3 units of Size M (which now has only 2) -> must fail HTTP 400
    fail_res = await async_client.post(
        "/api/v1/commerce/orders",
        json={
            "items": [
                {
                    "product_id": str(prod_id),
                    "quantity": 3,
                    "variant_sku": "RBR-JKT-M-BLK",
                }
            ],
            "payment_method": "CASH_ON_DELIVERY",
            "shipping_address": "Carrera 7 #71-21, Bogotá",
            "idempotency_key": f"order-variant-fail-{uuid4()}",
        },
        headers=headers,
    )
    assert fail_res.status_code == 400
    assert "RBR-JKT-M-BLK" in fail_res.json()["detail"]


async def test_cross_sell_bundle_recommendation_and_cogs_floor(
    async_client: AsyncClient,
) -> None:
    """Verifies smart cross-sell bundle recommendations and COGS margin floor protection (Law 3)."""
    from app.modules.commerce.domain.entities import (
        Product,
        build_smart_bundle_recommendation,
    )

    # 1. Unit Domain Test: Margin floor protection
    anchor = Product(
        merchant_id=uuid4(),
        sku="ANCHOR-COGS-TEST",
        title="Chaqueta Premium",
        description="Jacket",
        price_cents=100_000,
        unit_cost_cents=90_000,  # High COGS
        stock_quantity=10,
        category_tag="MENSWEAR",
        complement_tags=("MENSWEAR",),
    )
    complement = Product(
        merchant_id=uuid4(),
        sku="COMP-COGS-TEST",
        title="Pantalón Premium",
        description="Pants",
        price_cents=100_000,
        unit_cost_cents=90_000,  # High COGS -> combined COGS = 180,000 cents
        stock_quantity=10,
        category_tag="MENSWEAR",
    )
    # Total price = 200,000 cents. 12% discount would be 176,000 cents.
    # But combined COGS floor is 180,000 * 1.20 = 216,000 cents.
    # Therefore, final bundle price must clamp to min_protected_cents (216,000).
    bundle = build_smart_bundle_recommendation(
        anchor_product=anchor,
        catalog=[anchor, complement],
        bundle_discount_pct=12,
    )
    assert bundle is not None
    assert bundle["combined_cogs_cents"] == 180_000
    min_floor = (180_000 * 120 + 99) // 100
    assert bundle["bundle_price_cents"] >= min_floor

    # 2. Integration / API test: GET /api/v1/commerce/products/{id}/cross-sell
    unique_email = f"crosssell_{uuid4().hex[:6]}@superapp.io"
    await async_client.post(
        "/api/v1/identity/register",
        json={
            "email": unique_email,
            "password": "Password123!",
            "full_name": "Cross Sell Merchant",
            "roles": ["USER", "MERCHANT"],
        },
    )
    login_res = await async_client.post(
        "/api/v1/identity/login",
        json={"email": unique_email, "password": "Password123!"},
    )
    headers = {"Authorization": f"Bearer {login_res.json()['access_token']}"}

    res_jacket = await async_client.post(
        "/api/v1/commerce/products",
        json={
            "sku": f"JKT-{uuid4().hex[:6].upper()}",
            "title": "Chaqueta Bomber Street",
            "description": "Bomber",
            "price_cents": 180_000_00,  # $180,000 COP
            "unit_cost_cents": 75_000_00,  # COGS $75,000 COP
            "stock_quantity": 5,
            "category_tag": "MENSWEAR",
            "complement_tags": ["MENSWEAR"],
        },
        headers=headers,
    )
    assert res_jacket.status_code == 201
    jacket_id = res_jacket.json()["id"]

    res_pants = await async_client.post(
        "/api/v1/commerce/products",
        json={
            "sku": f"PNT-{uuid4().hex[:6].upper()}",
            "title": "Pantalón Cargo Tech",
            "description": "Cargo Pants",
            "price_cents": 140_000_00,  # $140,000 COP
            "unit_cost_cents": 60_000_00,  # COGS $60,000 COP
            "stock_quantity": 8,
            "category_tag": "MENSWEAR",
            "complement_tags": ["MENSWEAR"],
        },
        headers=headers,
    )
    assert res_pants.status_code == 201
    pants_id = res_pants.json()["id"]

    cross_res = await async_client.get(f"/api/v1/commerce/products/{jacket_id}/cross-sell")
    assert cross_res.status_code == 200
    data = cross_res.json()
    assert data is not None
    assert data["anchor_product_id"] == jacket_id
    assert data["complement_product_id"] == pants_id
    assert "Combo Outfit IA" in data["bundle_name"]
    assert data["original_total_cents"] == 320_000_00
    assert data["bundle_price_cents"] < 320_000_00
    assert data["savings_cents"] > 0


async def test_vip_free_shipping_benefit(
    async_client: AsyncClient,
) -> None:
    """Verifies that buyers with BRONZE tier pay shipping, but after reaching SILVER tier,

    they automatically receive free shipping ($0 shipping_cost_cents) on subsequent orders.
    """
    # 1. Register merchant and create product ($300,000 COP, COGS $120,000 COP)
    merchant_email = f"merchant_{uuid4().hex[:6]}@superapp.io"
    await async_client.post(
        "/api/v1/identity/register",
        json={
            "email": merchant_email,
            "password": "MerchantPassword123!",
            "full_name": "VIP Merchant",
            "roles": ["USER", "MERCHANT"],
        },
    )
    m_login = await async_client.post(
        "/api/v1/identity/login",
        json={"email": merchant_email, "password": "MerchantPassword123!"},
    )
    m_headers = {"Authorization": f"Bearer {m_login.json()['access_token']}"}

    prod_res = await async_client.post(
        "/api/v1/commerce/products",
        json={
            "sku": f"VIP-PROD-{uuid4().hex[:4].upper()}",
            "title": "Escritorio Elevable Ergonómico Motorizado",
            "description": "Escritorio premium eléctrico",
            "price_cents": 300_000_00,  # $300,000 COP
            "unit_cost_cents": 120_000_00,  # COGS $120,000 COP
            "stock_quantity": 10,
        },
        headers=m_headers,
    )
    assert prod_res.status_code == 201
    product_id = prod_res.json()["id"]

    # 2. Register buyer and check initial BRONZE status
    buyer_email = f"vip_buyer_{uuid4().hex[:6]}@superapp.io"
    await async_client.post(
        "/api/v1/identity/register",
        json={
            "email": buyer_email,
            "password": "BuyerPassword123!",
            "full_name": "Carlos Comprador",
            "roles": ["USER"],
        },
    )
    b_login = await async_client.post(
        "/api/v1/identity/login",
        json={"email": buyer_email, "password": "BuyerPassword123!"},
    )
    b_headers = {"Authorization": f"Bearer {b_login.json()['access_token']}"}

    b_wallet_0 = (await async_client.get("/api/v1/wallet/me", headers=b_headers)).json()
    assert b_wallet_0["wallet"]["loyalty_tier"] == "BRONZE"
    assert b_wallet_0["wallet"]["loyalty_points"] == 0
    assert b_wallet_0["wallet"]["lifetime_volume_cents"] == 0

    # 3. Buyer places first order as BRONZE -> shipping cost of $15,000 COP (1_500_000 cents) IS charged
    order_1_res = await async_client.post(
        "/api/v1/commerce/orders",
        json={
            "items": [{"product_id": product_id, "quantity": 1}],
            "payment_method": "CASH_ON_DELIVERY",
            "shipping_address": "Carrera 15 #85-12, Bogotá",
            "shipping_cost_cents": 1_500_000,
            "idempotency_key": f"vip-order-1-{uuid4().hex[:6]}",
        },
        headers=b_headers,
    )
    assert order_1_res.status_code == 201
    order_1 = order_1_res.json()
    assert order_1["shipping_cost_cents"] == 1_500_000  # Paid shipping
    assert order_1["total_cents"] == 300_000_00

    # 4. Merchant delivers order 1 -> reactive handler triggers 3% cashback and updates loyalty tier
    deliver_res = await async_client.post(
        f"/api/v1/commerce/orders/{order_1['id']}/deliver",
        headers=m_headers,
    )
    assert deliver_res.status_code == 200

    # 5. Verify buyer has been promoted to SILVER tier with 3% cashback
    # 3% of 30,000,000 cents = 900,000 points ($9,000 COP cashback)
    b_wallet_1 = (await async_client.get("/api/v1/wallet/me", headers=b_headers)).json()
    assert b_wallet_1["wallet"]["loyalty_tier"] == "SILVER"
    assert b_wallet_1["wallet"]["loyalty_points"] == 900_000
    assert b_wallet_1["wallet"]["lifetime_volume_cents"] == 300_000_00

    # 6. Buyer places second order -> Even if 1_500_000 shipping is requested, SILVER tier gets FREE SHIPPING!
    order_2_res = await async_client.post(
        "/api/v1/commerce/orders",
        json={
            "items": [{"product_id": product_id, "quantity": 1}],
            "payment_method": "CASH_ON_DELIVERY",
            "shipping_address": "Carrera 15 #85-12, Bogotá",
            "shipping_cost_cents": 1_500_000,
            "idempotency_key": f"vip-order-2-{uuid4().hex[:6]}",
        },
        headers=b_headers,
    )
    assert order_2_res.status_code == 201
    order_2 = order_2_res.json()
    assert order_2["shipping_cost_cents"] == 0  # Automatically zeroed out by SILVER benefit!
    # Net profit for merchant: 300,000 - 120,000 COGS - 0 shipping = 180,000 COP (18_000_000 cents)
    assert order_2["net_profit_cents"] == 18_000_000


async def test_concurrent_variant_orders_prevent_overselling_and_corrupt_ledger(
    async_client: AsyncClient,
) -> None:
    """Stress/Concurrency test: verifies that multiple simultaneous order requests for a

    limited-stock SKU variant never oversell inventory and keep the wallet balance & ledger consistent.
    """
    import asyncio

    # 1. Register Merchant
    m_email = f"stress_merchant_{uuid4().hex[:6]}@superapp.io"
    await async_client.post(
        "/api/v1/identity/register",
        json={
            "email": m_email,
            "password": "Password123!",
            "full_name": "Concurrency Merchant",
            "roles": ["USER", "MERCHANT"],
        },
    )
    m_login = await async_client.post(
        "/api/v1/identity/login",
        json={"email": m_email, "password": "Password123!"},
    )
    m_headers = {"Authorization": f"Bearer {m_login.json()['access_token']}"}

    # 2. Create product with limited variant stock: 3 units of size "M"
    from app.core.database import get_session_factory
    from app.modules.commerce.domain.entities import Product, ProductVariant
    from app.modules.commerce.infrastructure.repositories import (
        SqlAlchemyProductRepository,
    )

    unit_price = 50_000_00  # $50,000 COP
    initial_stock = 3
    product = Product(
        merchant_id=uuid4(),
        sku=f"CONCUR-TSHIRT-{uuid4().hex[:4].upper()}",
        title="Camiseta Oversize Edición Limitada",
        description="Stock ultralimitado de 3 unidades",
        price_cents=unit_price,
        unit_cost_cents=20_000_00,
        stock_quantity=initial_stock,
        variants=(
            ProductVariant(
                variant_sku="TSHIRT-LTD-M-BLK",
                size="M",
                color="Negro",
                stock_quantity=initial_stock,
            ),
        ),
    )
    factory = get_session_factory()
    async with factory() as session:
        repo = SqlAlchemyProductRepository(session)
        saved_prod = await repo.save(product)
        product_id = str(saved_prod.id)

    # 3. Register Buyer with abundant wallet balance (500,000 COP = 50,000,000 cents)
    b_email = f"stress_buyer_{uuid4().hex[:6]}@superapp.io"
    await async_client.post(
        "/api/v1/identity/register",
        json={
            "email": b_email,
            "password": "Password123!",
            "full_name": "Concurrency Buyer",
            "roles": ["USER"],
        },
    )
    b_login = await async_client.post(
        "/api/v1/identity/login",
        json={"email": b_email, "password": "Password123!"},
    )
    b_headers = {"Authorization": f"Bearer {b_login.json()['access_token']}"}

    initial_deposit = 500_000_00
    topup_res = await async_client.post(
        "/api/v1/wallet/me/deposit",
        json={
            "amount_cents": initial_deposit,
            "reference": "Topup for stress test",
            "idempotency_key": f"topup-{uuid4()}",
        },
        headers=b_headers,
    )
    assert topup_res.status_code == 201

    # 4. Trigger 7 concurrent buy requests for 1 unit of variant "TSHIRT-LTD-M-BLK"
    concurrent_requests = 7

    async def place_single_order(idx: int):
        return await async_client.post(
            "/api/v1/commerce/orders",
            json={
                "items": [
                    {
                        "product_id": product_id,
                        "quantity": 1,
                        "variant_sku": "TSHIRT-LTD-M-BLK",
                    }
                ],
                "payment_method": "WALLET",
                "shipping_address": "Carrera 7 #72-13, Bogotá",
                "idempotency_key": f"concur-order-{idx}-{uuid4().hex[:6]}",
            },
            headers=b_headers,
        )

    responses = await asyncio.gather(
        *(place_single_order(i) for i in range(concurrent_requests))
    )

    # 5. Assertions:
    # Confirmed orders must NOT exceed the available stock (3)
    confirmed = [r for r in responses if r.status_code == 201]
    rejected = [r for r in responses if r.status_code != 201]

    assert len(confirmed) <= initial_stock, (
        f"Overselling detected! {len(confirmed)} orders confirmed for only {initial_stock} units."
    )
    assert len(confirmed) + len(rejected) == concurrent_requests

    # Every rejected request must cleanly return domain error (400 Insufficient stock)
    for r in rejected:
        assert r.status_code in (400, 409), f"Unexpected status code: {r.status_code}: {r.text}"
        assert "Insufficient stock" in r.json().get("detail", "")

    # 6. Verify inventory state: depleted stock is excluded from active catalog and zeroed in DB
    cat_res = await async_client.get("/api/v1/commerce/products")
    assert not any(p["id"] == product_id for p in cat_res.json())

    from app.core.database import get_session_factory
    from app.modules.commerce.infrastructure.repositories import (
        SqlAlchemyProductRepository,
    )

    factory = get_session_factory()
    async with factory() as session:
        repo = SqlAlchemyProductRepository(session)
        product_after = await repo.get_by_id(UUID(product_id))
        assert product_after is not None
        assert product_after.stock_quantity == initial_stock - len(confirmed)
        variant_m = next(
            v for v in product_after.variants if v.variant_sku == "TSHIRT-LTD-M-BLK"
        )
        assert variant_m.stock_quantity == initial_stock - len(confirmed)
        assert variant_m.stock_quantity >= 0

    # 7. Verify buyer Wallet balance and Ledger integrity
    wallet_res = await async_client.get("/api/v1/wallet/me", headers=b_headers)
    assert wallet_res.status_code == 200
    wallet_data = wallet_res.json()

    expected_balance = initial_deposit - (len(confirmed) * unit_price)
    assert wallet_data["wallet"]["balance_cents"] == expected_balance

    # Ensure ledger entries strictly reflect confirmed orders
    debit_entries = [
        e for e in wallet_data["recent_entries"] if e["transaction_type"] == "DEBIT"
    ]
    assert len(debit_entries) == len(confirmed)


async def test_catalog_search_and_category_filtering(
    async_client: AsyncClient,
) -> None:
    """Verifies searching by query (case-insensitive title/SKU) and filtering by category_tag."""
    # 1. Register and authenticate merchant
    await async_client.post(
        "/api/v1/identity/register",
        json={
            "email": "catalog_search_merchant@superapp.io",
            "password": "Password123!",
            "full_name": "Search Merchant",
            "roles": ["USER", "MERCHANT"],
        },
    )
    login_res = await async_client.post(
        "/api/v1/identity/login",
        json={
            "email": "catalog_search_merchant@superapp.io",
            "password": "Password123!",
        },
    )
    headers = {"Authorization": f"Bearer {login_res.json()['access_token']}"}

    # 2. Create products with distinct categories and titles
    p1 = await async_client.post(
        "/api/v1/commerce/products",
        json={
            "sku": "HOODIE-OVSZ-01",
            "title": "Hoodie Oversize Negro",
            "description": "Algodón pesado 400g",
            "price_cents": 18_000_000,
            "unit_cost_cents": 8_000_000,
            "stock_quantity": 10,
            "category_tag": "MENSWEAR",
        },
        headers=headers,
    )
    assert p1.status_code == 201

    p2 = await async_client.post(
        "/api/v1/commerce/products",
        json={
            "sku": "DESK-MAT-RGB",
            "title": "Desk Mat RGB Pro",
            "description": "Superficie micro-texturizada",
            "price_cents": 12_000_000,
            "unit_cost_cents": 5_000_000,
            "stock_quantity": 5,
            "category_tag": "DESK_SETUP",
        },
        headers=headers,
    )
    assert p2.status_code == 201

    p3 = await async_client.post(
        "/api/v1/commerce/products",
        json={
            "sku": "MUG-DEV-CERAMIC",
            "title": "Taza de Café Developer",
            "description": "Cerámica artesanal",
            "price_cents": 4_500_000,
            "unit_cost_cents": 1_500_000,
            "stock_quantity": 8,
            "category_tag": "GENERAL",
        },
        headers=headers,
    )
    assert p3.status_code == 201

    # 3. Test unfiltered catalog
    all_res = await async_client.get("/api/v1/commerce/products")
    assert all_res.status_code == 200
    all_skus = {p["sku"] for p in all_res.json()}
    assert {"HOODIE-OVSZ-01", "DESK-MAT-RGB", "MUG-DEV-CERAMIC"}.issubset(all_skus)

    # 4. Test category filtering (MENSWEAR)
    menswear_res = await async_client.get(
        "/api/v1/commerce/products", params={"category_tag": "MENSWEAR"}
    )
    assert menswear_res.status_code == 200
    menswear_skus = [p["sku"] for p in menswear_res.json()]
    assert "HOODIE-OVSZ-01" in menswear_skus
    assert "DESK-MAT-RGB" not in menswear_skus
    assert "MUG-DEV-CERAMIC" not in menswear_skus

    # 5. Test category filtering (DESK_SETUP)
    desk_res = await async_client.get(
        "/api/v1/commerce/products", params={"category_tag": "DESK_SETUP"}
    )
    assert desk_res.status_code == 200
    desk_skus = [p["sku"] for p in desk_res.json()]
    assert "DESK-MAT-RGB" in desk_skus
    assert "HOODIE-OVSZ-01" not in desk_skus

    # 6. Test search filter by title keyword (case-insensitive "hoodie")
    search_hoodie = await async_client.get(
        "/api/v1/commerce/products", params={"search": "hoodie"}
    )
    assert search_hoodie.status_code == 200
    hoodie_skus = [p["sku"] for p in search_hoodie.json()]
    assert "HOODIE-OVSZ-01" in hoodie_skus
    assert "DESK-MAT-RGB" not in hoodie_skus

    # 7. Test search filter by SKU keyword (case-insensitive "ceramic")
    search_ceramic = await async_client.get(
        "/api/v1/commerce/products", params={"search": "ceramic"}
    )
    assert search_ceramic.status_code == 200
    ceramic_skus = [p["sku"] for p in search_ceramic.json()]
    assert "MUG-DEV-CERAMIC" in ceramic_skus
    assert "HOODIE-OVSZ-01" not in ceramic_skus

    # 8. Test combined search & category filter (matching)
    combined_match = await async_client.get(
        "/api/v1/commerce/products",
        params={"search": "negro", "category_tag": "MENSWEAR"},
    )
    assert combined_match.status_code == 200
    assert any(p["sku"] == "HOODIE-OVSZ-01" for p in combined_match.json())

    # 9. Test combined search & category filter (non-matching combination)
    combined_nomatch = await async_client.get(
        "/api/v1/commerce/products",
        params={"search": "negro", "category_tag": "DESK_SETUP"},
    )
    assert combined_nomatch.status_code == 200
    assert not any(p["sku"] == "HOODIE-OVSZ-01" for p in combined_nomatch.json())

    # 10. Non-existent query returns empty list
    nonexistent = await async_client.get(
        "/api/v1/commerce/products", params={"search": "inexistente_xyz_99"}
    )
    assert nonexistent.status_code == 200
    assert len(nonexistent.json()) == 0



