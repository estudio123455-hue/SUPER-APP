"""Unit and integration tests for the Wallet module and its EventBus integration with Identity."""

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
from app.modules.identity.infrastructure.models import IdentityBase
from app.modules.wallet.application.handlers import register_wallet_event_handlers
from app.modules.wallet.domain.entities import Wallet
from app.modules.wallet.domain.exceptions import (
    InsufficientFundsError,
    WalletLockedError,
)
from app.modules.wallet.infrastructure.models import LedgerEntryModel, WalletBase, WalletModel


@pytest.fixture
async def sqlite_engine() -> AsyncGenerator[AsyncEngine, None]:
    """Creates a shared in-memory SQLite engine for both identity_schema and wallet_schema."""
    base_engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        execution_options={"schema_translate_map": SQLITE_SCHEMA_TRANSLATE_MAP},
    )
    async with base_engine.begin() as conn:
        await conn.run_sync(IdentityBase.metadata.create_all)
        await conn.run_sync(WalletBase.metadata.create_all)
    yield base_engine
    await base_engine.dispose()


@pytest.fixture
async def async_client(sqlite_engine: AsyncEngine) -> AsyncGenerator[AsyncClient, None]:
    """Configures test session factory, registers Wallet EventBus handlers, and yields client."""
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


def test_wallet_domain_invariants_and_schema_isolation() -> None:
    """Verifies pure domain Wallet rules and Law 2 schema isolation (no cross-schema FKs)."""
    assert WalletModel.__table__.schema == "wallet_schema"
    assert LedgerEntryModel.__table__.schema == "wallet_schema"
    assert len(WalletModel.__table__.foreign_keys) == 0
    assert len(LedgerEntryModel.__table__.foreign_keys) == 0

    wallet = Wallet(user_id=uuid4(), currency="cop", balance_cents=0)
    assert wallet.currency == "COP"

    credited_wallet, credit_entry = wallet.credit(
        amount_cents=150_00,
        reference="Initial Top-up",
        idempotency_key="key-001",
    )
    assert credited_wallet.balance_cents == 150_00
    assert credit_entry.amount_cents == 150_00

    debited_wallet, debit_entry = credited_wallet.debit(
        amount_cents=50_00,
        reference="Purchase #1",
        idempotency_key="key-002",
    )
    assert debited_wallet.balance_cents == 100_00
    assert debit_entry.amount_cents == 50_00

    with pytest.raises(InsufficientFundsError):
        debited_wallet.debit(
            amount_cents=200_00,
            reference="Overdraft attempt",
            idempotency_key="key-003",
        )

    locked_wallet = Wallet(
        user_id=wallet.user_id,
        currency="COP",
        balance_cents=100_00,
        is_locked=True,
    )
    with pytest.raises(WalletLockedError):
        locked_wallet.credit(
            amount_cents=10_00,
            reference="Locked credit",
            idempotency_key="key-004",
        )


async def test_user_registration_automatically_creates_wallet(
    async_client: AsyncClient,
) -> None:
    """Verifies that registering a user in Identity triggers Wallet creation via EventBus."""
    reg_res = await async_client.post(
        "/api/v1/identity/register",
        json={
            "email": "wallet_owner@superapp.io",
            "password": "SecurePassword123!",
            "full_name": "Satoshi Nakamoto",
            "roles": ["USER"],
        },
    )
    assert reg_res.status_code == 201
    user_id = reg_res.json()["id"]

    login_res = await async_client.post(
        "/api/v1/identity/login",
        json={
            "email": "wallet_owner@superapp.io",
            "password": "SecurePassword123!",
        },
    )
    assert login_res.status_code == 200
    token = login_res.json()["access_token"]

    wallet_res = await async_client.get(
        "/api/v1/wallet/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert wallet_res.status_code == 200
    data = wallet_res.json()
    assert data["wallet"]["user_id"] == user_id
    assert data["wallet"]["currency"] == "COP"
    assert data["wallet"]["balance_cents"] == 0
    assert data["wallet"]["is_locked"] is False
    assert data["recent_entries"] == []


async def test_deposit_idempotency_and_withdraw_insufficient_funds(
    async_client: AsyncClient,
) -> None:
    """Verifies deposit, duplicate idempotency_key protection, withdrawal, and overdraft error."""
    await async_client.post(
        "/api/v1/identity/register",
        json={
            "email": "trader@superapp.io",
            "password": "TraderPassword123!",
            "full_name": "David Ricardo",
            "roles": ["USER"],
        },
    )
    login_res = await async_client.post(
        "/api/v1/identity/login",
        json={
            "email": "trader@superapp.io",
            "password": "TraderPassword123!",
        },
    )
    headers = {"Authorization": f"Bearer {login_res.json()['access_token']}"}

    # 1. Successful deposit of 100,000.00 COP (10_000_000 cents)
    deposit_payload = {
        "amount_cents": 10_000_000,
        "reference": "PSE Recharge #1001",
        "idempotency_key": "pse-recharge-1001",
    }
    dep_res = await async_client.post(
        "/api/v1/wallet/me/deposit",
        json=deposit_payload,
        headers=headers,
    )
    assert dep_res.status_code == 201
    dep_data = dep_res.json()
    assert dep_data["wallet"]["balance_cents"] == 10_000_000
    assert dep_data["entry"]["transaction_type"] == "CREDIT"
    assert dep_data["entry"]["idempotency_key"] == "pse-recharge-1001"

    # 2. Sending the exact same idempotency_key again MUST return 409 and NOT double the balance
    dup_res = await async_client.post(
        "/api/v1/wallet/me/deposit",
        json=deposit_payload,
        headers=headers,
    )
    assert dup_res.status_code == 409

    check_res = await async_client.get("/api/v1/wallet/me", headers=headers)
    assert check_res.json()["wallet"]["balance_cents"] == 10_000_000
    assert len(check_res.json()["recent_entries"]) == 1

    # 3. Successful withdrawal of 40,000.00 COP (4_000_000 cents)
    withdraw_res = await async_client.post(
        "/api/v1/wallet/me/withdraw",
        json={
            "amount_cents": 4_000_000,
            "reference": "ATM Withdrawal #2001",
            "idempotency_key": "atm-withdraw-2001",
        },
        headers=headers,
    )
    assert withdraw_res.status_code == 201
    assert withdraw_res.json()["wallet"]["balance_cents"] == 6_000_000

    # 4. Attempting to withdraw 90,000.00 COP (9_000_000 cents > 6_000_000 available) -> 400
    overdraft_res = await async_client.post(
        "/api/v1/wallet/me/withdraw",
        json={
            "amount_cents": 9_000_000,
            "reference": "Excessive Withdrawal",
            "idempotency_key": "atm-withdraw-2002",
        },
        headers=headers,
    )
    assert overdraft_res.status_code == 400
    assert "Insufficient funds" in overdraft_res.json()["detail"]

    # Final balance remains untouched at 6_000_000 cents with 2 ledger entries
    final_res = await async_client.get("/api/v1/wallet/me", headers=headers)
    final_data = final_res.json()
    assert final_data["wallet"]["balance_cents"] == 6_000_000
    assert len(final_data["recent_entries"]) == 2


async def test_payment_gateway_webhook_hmac_validation_and_idempotency(
    async_client: AsyncClient,
) -> None:
    """Verifies HMAC-SHA256 signature verification, 401 on tampered payload, and idempotent credit."""
    import json
    from app.modules.wallet.infrastructure.security import compute_payment_webhook_signature

    reg_res = await async_client.post(
        "/api/v1/identity/register",
        json={
            "email": "gateway_client@superapp.io",
            "password": "GatewayPassword123!",
            "full_name": "Gateway Client",
            "roles": ["USER"],
        },
    )
    assert reg_res.status_code == 201
    user_id = reg_res.json()["id"]

    login_res = await async_client.post(
        "/api/v1/identity/login",
        json={
            "email": "gateway_client@superapp.io",
            "password": "GatewayPassword123!",
        },
    )
    auth_header = {"Authorization": f"Bearer {login_res.json()['access_token']}"}

    payload = {
        "event_id": "wompi-pay-998811",
        "user_id": user_id,
        "amount_cents": 15_000_000,
        "provider": "WOMPI",
    }
    raw_body = json.dumps(payload).encode("utf-8")

    # 1. Missing or invalid signature returns 401 Unauthorized
    tampered_res = await async_client.post(
        "/api/v1/wallet/webhooks/payment-gateway",
        content=raw_body,
        headers={
            "Content-Type": "application/json",
            "X-Webhook-Signature": "invalid_fake_signature_hex",
        },
    )
    assert tampered_res.status_code == 401
    assert "Invalid or missing X-Webhook-Signature" in tampered_res.json()["detail"]

    no_sig_res = await async_client.post(
        "/api/v1/wallet/webhooks/payment-gateway",
        content=raw_body,
        headers={"Content-Type": "application/json"},
    )
    assert no_sig_res.status_code == 401

    # 2. Valid HMAC-SHA256 signature credits the wallet
    valid_sig = compute_payment_webhook_signature(raw_body)
    ok_res = await async_client.post(
        "/api/v1/wallet/webhooks/payment-gateway",
        content=raw_body,
        headers={
            "Content-Type": "application/json",
            "X-Webhook-Signature": valid_sig,
        },
    )
    assert ok_res.status_code == 200
    ok_data = ok_res.json()
    assert ok_data["wallet"]["balance_cents"] == 15_000_000
    assert ok_data["entry"]["amount_cents"] == 15_000_000
    assert ok_data["entry"]["transaction_type"] == "CREDIT"
    assert ok_data["entry"]["idempotency_key"] == "wompi-pay-998811"
    assert ok_data["provider"] == "WOMPI"
    assert ok_data["already_processed"] is False

    # 3. Gateway retry with exact same event_id is idempotent (200 OK, already_processed=True, balance not doubled)
    retry_res = await async_client.post(
        "/api/v1/wallet/webhooks/payment-gateway",
        content=raw_body,
        headers={
            "Content-Type": "application/json",
            "X-Webhook-Signature": valid_sig,
        },
    )
    assert retry_res.status_code == 200
    retry_data = retry_res.json()
    assert retry_data["wallet"]["balance_cents"] == 15_000_000
    assert retry_data["already_processed"] is True

    # 4. Verify user wallet state
    me_res = await async_client.get("/api/v1/wallet/me", headers=auth_header)
    assert me_res.status_code == 200
    me_data = me_res.json()
    assert me_data["wallet"]["balance_cents"] == 15_000_000
    assert len(me_data["recent_entries"]) == 1
    assert me_data["recent_entries"][0]["idempotency_key"] == "wompi-pay-998811"


async def test_loyalty_cashback_tier_upgrade_and_redemption(
    async_client: AsyncClient,
) -> None:
    """Verifies 3% cashback accumulation, VIP tier transitions (BRONZE -> SILVER -> GOLD), and point redemption to COP."""
    from app.modules.commerce.public_api import OrderDeliveredAndSettledEvent

    email = f"vip_buyer_{uuid4().hex[:8]}@superapp.co"
    reg_res = await async_client.post(
        "/api/v1/identity/register",
        json={
            "email": email,
            "password": "VipPassword123!",
            "full_name": "VIP Customer",
            "roles": ["USER"],
        },
    )
    user_id = reg_res.json()["id"]
    login_res = await async_client.post(
        "/api/v1/identity/login",
        json={"email": email, "password": "VipPassword123!"},
    )
    headers = {"Authorization": f"Bearer {login_res.json()['access_token']}"}

    # Initial state: BRONZE, 0 points, 0 volume
    me_res = await async_client.get("/api/v1/wallet/me", headers=headers)
    assert me_res.status_code == 200
    w_init = me_res.json()["wallet"]
    assert w_init["loyalty_tier"] == "BRONZE"
    assert w_init["loyalty_points"] == 0
    assert w_init["lifetime_volume_cents"] == 0

    # 1. First delivered order: $100,000 COP (10,000,000 cents) -> 3% cashback = 300,000 pts ($3,000 COP)
    order1_id = uuid4()
    merchant_id = uuid4()
    await event_bus.publish(
        OrderDeliveredAndSettledEvent(
            order_id=order1_id,
            merchant_id=merchant_id,
            buyer_id=UUID(user_id),
            payment_method="CASH_ON_DELIVERY",
            gross_total_cents=10_000_000,
            total_cogs_cents=4_000_000,
            shipping_cost_cents=1_200_000,
            net_profit_cents=4_800_000,
        )
    )

    me_res1 = await async_client.get("/api/v1/wallet/me", headers=headers)
    w1 = me_res1.json()["wallet"]
    assert w1["loyalty_tier"] == "BRONZE"
    assert w1["loyalty_points"] == 300_000
    assert w1["lifetime_volume_cents"] == 10_000_000

    # Duplicate delivery event is idempotent
    await event_bus.publish(
        OrderDeliveredAndSettledEvent(
            order_id=order1_id,
            merchant_id=merchant_id,
            buyer_id=UUID(user_id),
            payment_method="CASH_ON_DELIVERY",
            gross_total_cents=10_000_000,
            total_cogs_cents=4_000_000,
            shipping_cost_cents=1_200_000,
            net_profit_cents=4_800_000,
        )
    )
    me_res1_dup = await async_client.get("/api/v1/wallet/me", headers=headers)
    assert me_res1_dup.json()["wallet"]["loyalty_points"] == 300_000

    # 2. Second order of $250,000 COP (25,000,000 cents) -> cumulative = $350,000 COP -> Upgrades to SILVER!
    order2_id = uuid4()
    await event_bus.publish(
        OrderDeliveredAndSettledEvent(
            order_id=order2_id,
            merchant_id=merchant_id,
            buyer_id=UUID(user_id),
            payment_method="CASH_ON_DELIVERY",
            gross_total_cents=25_000_000,
            total_cogs_cents=10_000_000,
            shipping_cost_cents=1_200_000,
            net_profit_cents=13_800_000,
        )
    )

    me_res2 = await async_client.get("/api/v1/wallet/me", headers=headers)
    w2 = me_res2.json()["wallet"]
    assert w2["loyalty_tier"] == "SILVER"
    # 300,000 + 750,000 = 1,050,000 points
    assert w2["loyalty_points"] == 1_050_000
    assert w2["lifetime_volume_cents"] == 35_000_000

    # 3. Third order of $700,000 COP (70,000,000 cents) -> cumulative = $1,050,000 COP -> Upgrades to GOLD!
    order3_id = uuid4()
    await event_bus.publish(
        OrderDeliveredAndSettledEvent(
            order_id=order3_id,
            merchant_id=merchant_id,
            buyer_id=UUID(user_id),
            payment_method="CASH_ON_DELIVERY",
            gross_total_cents=70_000_000,
            total_cogs_cents=30_000_000,
            shipping_cost_cents=1_200_000,
            net_profit_cents=38_800_000,
        )
    )

    me_res3 = await async_client.get("/api/v1/wallet/me", headers=headers)
    w3 = me_res3.json()["wallet"]
    assert w3["loyalty_tier"] == "GOLD"
    # 1,050,000 + 2,100,000 = 3,150,000 points
    assert w3["loyalty_points"] == 3_150_000

    # 4. Redeem points: converts 3,150,000 points into $31,500 COP liquid balance
    redeem_res = await async_client.post("/api/v1/wallet/me/redeem-points", headers=headers)
    assert redeem_res.status_code == 200
    r_data = redeem_res.json()
    assert r_data["wallet"]["balance_cents"] == 3_150_000
    assert r_data["wallet"]["loyalty_points"] == 0
    assert r_data["entry"]["amount_cents"] == 3_150_000
    assert r_data["entry"]["transaction_type"] == "CREDIT"

    # Attempting to redeem again with 0 points fails with 400 Bad Request
    empty_redeem = await async_client.post("/api/v1/wallet/me/redeem-points", headers=headers)
    assert empty_redeem.status_code == 400

