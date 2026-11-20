"""Unit and integration tests for the Identity module (Domain, Application, API & EventBus)."""

from collections.abc import AsyncGenerator
import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.database import SQLITE_SCHEMA_TRANSLATE_MAP, get_db_session
from app.core.event_bus import event_bus
from app.main import app
from app.modules.identity.application.events import UserRegisteredEvent
from app.modules.identity.domain.entities import User, UserRole
from app.modules.identity.infrastructure.models import IdentityBase, UserModel


@pytest.fixture
async def sqlite_engine() -> AsyncGenerator[AsyncEngine, None]:
    """Creates an in-memory SQLite async engine translating PostgreSQL schemas to None."""
    base_engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        execution_options={"schema_translate_map": SQLITE_SCHEMA_TRANSLATE_MAP},
    )
    async with base_engine.begin() as conn:
        await conn.run_sync(IdentityBase.metadata.create_all)
    yield base_engine
    await base_engine.dispose()


@pytest.fixture
async def db_session(sqlite_engine: AsyncEngine) -> AsyncGenerator[AsyncSession, None]:
    """Provides an isolated SQLite AsyncSession for each test."""
    session_factory = async_sessionmaker(
        bind=sqlite_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )
    async with session_factory() as session:
        yield session


@pytest.fixture
async def async_client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    """Provides an httpx AsyncClient wired to FastAPI with the test SQLite session."""

    async def _override_get_db() -> AsyncGenerator[AsyncSession, None]:
        yield db_session

    app.dependency_overrides[get_db_session] = _override_get_db
    event_bus.clear()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        yield client
    app.dependency_overrides.clear()
    event_bus.clear()


def test_user_domain_entity_immutability_and_normalization() -> None:
    """Verifies pure domain entity validation and immutability."""
    user = User(
        email="  Creator@SuperApp.io ",
        password_hash="hashed_secret",
        full_name="Ada Lovelace",
        roles=frozenset({UserRole.USER, UserRole.CREATOR}),
    )
    assert user.email == "creator@superapp.io"
    assert UserRole.CREATOR in user.roles
    assert UserModel.__table__.schema == "identity_schema"

    with pytest.raises(ValueError, match="Invalid email"):
        User(email="invalid-email", password_hash="hash", full_name="Invalid")


async def test_register_emits_event_and_prevents_duplicates(
    async_client: AsyncClient,
) -> None:
    """Verifies POST /api/v1/identity/register persists user and publishes UserRegisteredEvent."""
    published_events: list[UserRegisteredEvent] = []

    async def on_user_registered(event: UserRegisteredEvent) -> None:
        published_events.append(event)

    event_bus.subscribe(UserRegisteredEvent, on_user_registered)

    payload = {
        "email": "merchant@superapp.io",
        "password": "StrongPassword123!",
        "full_name": "Grace Hopper",
        "roles": ["USER", "MERCHANT"],
    }
    response = await async_client.post("/api/v1/identity/register", json=payload)
    assert response.status_code == 201
    data = response.json()
    assert data["email"] == "merchant@superapp.io"
    assert data["full_name"] == "Grace Hopper"
    assert set(data["roles"]) == {"USER", "MERCHANT"}
    assert data["is_active"] is True

    # Verify EventBus notification
    assert len(published_events) == 1
    assert published_events[0].email == "merchant@superapp.io"
    assert published_events[0].roles == ("MERCHANT", "USER")

    # Duplicate email must return 409 Conflict
    dup_response = await async_client.post("/api/v1/identity/register", json=payload)
    assert dup_response.status_code == 409


async def test_login_and_get_me_flow(async_client: AsyncClient) -> None:
    """Verifies JWT authentication flow: register -> login -> GET /me."""
    register_payload = {
        "email": "studio_user@superapp.io",
        "password": "MySecretPassword99",
        "full_name": "Alan Turing",
        "roles": ["USER", "CREATOR"],
    }
    reg_res = await async_client.post("/api/v1/identity/register", json=register_payload)
    assert reg_res.status_code == 201

    # Invalid password returns 401
    bad_login = await async_client.post(
        "/api/v1/identity/login",
        json={"email": "studio_user@superapp.io", "password": "WrongPassword"},
    )
    assert bad_login.status_code == 401

    # Valid login returns access_token & refresh_token
    login_res = await async_client.post(
        "/api/v1/identity/login",
        json={"email": "studio_user@superapp.io", "password": "MySecretPassword99"},
    )
    assert login_res.status_code == 200
    tokens = login_res.json()
    assert "access_token" in tokens
    assert "refresh_token" in tokens
    assert tokens["token_type"] == "bearer"

    # Access protected /me endpoint
    me_res = await async_client.get(
        "/api/v1/identity/me",
        headers={"Authorization": f"Bearer {tokens['access_token']}"},
    )
    assert me_res.status_code == 200
    me_data = me_res.json()
    assert me_data["email"] == "studio_user@superapp.io"
    assert set(me_data["roles"]) == {"USER", "CREATOR"}

    # Using refresh_token as access_token must be rejected with 401
    refresh_as_access = await async_client.get(
        "/api/v1/identity/me",
        headers={"Authorization": f"Bearer {tokens['refresh_token']}"},
    )
    assert refresh_as_access.status_code == 401


async def test_refresh_token_rotation_and_revocation(async_client: AsyncClient) -> None:
    """Verifies rotatable refresh tokens, reuse detection, and revocation on logout."""
    # 1. Register test user
    register_payload = {
        "email": "security_tester@superapp.io",
        "password": "SecurePassword#2026",
        "full_name": "Linus Torvalds",
        "roles": ["USER"],
    }
    reg_res = await async_client.post("/api/v1/identity/register", json=register_payload)
    assert reg_res.status_code == 201

    # 2. Login via /auth/login
    login_res = await async_client.post(
        "/api/v1/identity/auth/login",
        json={"email": "security_tester@superapp.io", "password": "SecurePassword#2026"},
    )
    assert login_res.status_code == 200
    token_pair_1 = login_res.json()
    assert "access_token" in token_pair_1
    assert "refresh_token" in token_pair_1
    rt_1 = token_pair_1["refresh_token"]

    # 3. Rotate refresh token via /api/v1/identity/auth/refresh
    refresh_res_1 = await async_client.post(
        "/api/v1/identity/auth/refresh",
        json={"refresh_token": rt_1},
    )
    assert refresh_res_1.status_code == 200
    token_pair_2 = refresh_res_1.json()
    rt_2 = token_pair_2["refresh_token"]
    at_2 = token_pair_2["access_token"]
    assert rt_2 != rt_1

    # Verify new access token works
    me_res = await async_client.get(
        "/api/v1/identity/me",
        headers={"Authorization": f"Bearer {at_2}"},
    )
    assert me_res.status_code == 200
    assert me_res.json()["email"] == "security_tester@superapp.io"

    # 4. Token Reuse Detection: Attempting to use old rt_1 must be rejected with 401
    reuse_res = await async_client.post(
        "/api/v1/identity/auth/refresh",
        json={"refresh_token": rt_1},
    )
    assert reuse_res.status_code == 401
    assert "revoked" in reuse_res.json()["detail"].lower()

    # 5. Invalid/Malformed refresh token must return 401
    bad_token_res = await async_client.post(
        "/api/v1/identity/auth/refresh",
        json={"refresh_token": "non_existent_or_invalid_refresh_token_string"},
    )
    assert bad_token_res.status_code == 401

    # 6. Re-authenticate to get clean session
    login_res_2 = await async_client.post(
        "/api/v1/identity/auth/login",
        json={"email": "security_tester@superapp.io", "password": "SecurePassword#2026"},
    )
    assert login_res_2.status_code == 200
    rt_3 = login_res_2.json()["refresh_token"]

    # 7. Logout via /api/v1/identity/auth/logout
    logout_res = await async_client.post(
        "/api/v1/identity/auth/logout",
        json={"refresh_token": rt_3},
    )
    assert logout_res.status_code == 200
    assert logout_res.json()["status"] == "logged_out"

    # 8. Refreshing with logged out token must fail with 401
    post_logout_refresh = await async_client.post(
        "/api/v1/identity/auth/refresh",
        json={"refresh_token": rt_3},
    )
    assert post_logout_refresh.status_code == 401

