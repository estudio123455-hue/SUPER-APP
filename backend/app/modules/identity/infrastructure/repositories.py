"""SQLAlchemy 2.0 implementation of UserRepository with Domain <-> ORM mappers."""

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.identity.domain.entities import RefreshToken, User, UserRole
from app.modules.identity.domain.repositories import (
    RefreshTokenRepository,
    UserRepository,
)
from app.modules.identity.infrastructure.models import RefreshTokenModel, UserModel



class SqlAlchemyUserRepository(UserRepository):
    """Adapter persisting User entities via SQLAlchemy 2.0 AsyncSession."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    @staticmethod
    def _to_domain(model: UserModel) -> User:
        raw_roles = [r.strip() for r in model.roles_csv.split(",") if r.strip()]
        roles = frozenset(UserRole(r) for r in raw_roles) or frozenset({UserRole.USER})
        created_at = model.created_at
        if created_at.tzinfo is None:
            created_at = created_at.replace(tzinfo=UTC)
        return User(
            id=model.id,
            email=model.email,
            password_hash=model.password_hash,
            full_name=model.full_name,
            roles=roles,
            is_active=model.is_active,
            created_at=created_at,
        )

    @staticmethod
    def _roles_to_csv(roles: frozenset[UserRole]) -> str:
        return ",".join(sorted(role.value for role in roles))

    async def get_by_id(self, user_id: UUID) -> User | None:
        stmt = select(UserModel).where(UserModel.id == user_id)
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        return self._to_domain(model) if model is not None else None

    async def get_by_email(self, email: str) -> User | None:
        normalized_email = email.strip().lower()
        stmt = select(UserModel).where(UserModel.email == normalized_email)
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        return self._to_domain(model) if model is not None else None

    async def save(self, user: User) -> User:
        stmt = select(UserModel).where(UserModel.id == user.id)
        result = await self._session.execute(stmt)
        existing = result.scalar_one_or_none()

        roles_csv = self._roles_to_csv(user.roles)
        if existing is None:
            model = UserModel(
                id=user.id,
                email=user.email,
                password_hash=user.password_hash,
                full_name=user.full_name,
                roles_csv=roles_csv,
                is_active=user.is_active,
                created_at=user.created_at,
            )
            self._session.add(model)
        else:
            existing.email = user.email
            existing.password_hash = user.password_hash
            existing.full_name = user.full_name
            existing.roles_csv = roles_csv
            existing.is_active = user.is_active
            model = existing

        await self._session.commit()
        await self._session.refresh(model)
        return self._to_domain(model)


class SqlAlchemyRefreshTokenRepository(RefreshTokenRepository):
    """Adapter persisting RefreshToken entities via SQLAlchemy 2.0 AsyncSession."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    @staticmethod
    def _to_domain(model: RefreshTokenModel) -> RefreshToken:
        created_at = model.created_at
        if created_at.tzinfo is None:
            created_at = created_at.replace(tzinfo=UTC)
        expires_at = model.expires_at
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=UTC)
        revoked_at = model.revoked_at
        if revoked_at is not None and revoked_at.tzinfo is None:
            revoked_at = revoked_at.replace(tzinfo=UTC)

        return RefreshToken(
            id=model.id,
            user_id=model.user_id,
            token_hash=model.token_hash,
            expires_at=expires_at,
            revoked_at=revoked_at,
            replaced_by_token_id=model.replaced_by_token_id,
            created_at=created_at,
        )

    async def get_by_hash(self, token_hash: str) -> RefreshToken | None:
        stmt = (
            select(RefreshTokenModel)
            .where(RefreshTokenModel.token_hash == token_hash)
            .execution_options(populate_existing=True)
        )
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        return self._to_domain(model) if model is not None else None

    async def get_by_id(self, token_id: UUID) -> RefreshToken | None:
        stmt = (
            select(RefreshTokenModel)
            .where(RefreshTokenModel.id == token_id)
            .execution_options(populate_existing=True)
        )
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        return self._to_domain(model) if model is not None else None

    async def save(self, token: RefreshToken) -> RefreshToken:
        stmt = (
            select(RefreshTokenModel)
            .where(RefreshTokenModel.id == token.id)
            .execution_options(populate_existing=True)
        )
        result = await self._session.execute(stmt)
        existing = result.scalar_one_or_none()

        if existing is None:
            model = RefreshTokenModel(
                id=token.id,
                user_id=token.user_id,
                token_hash=token.token_hash,
                expires_at=token.expires_at,
                revoked_at=token.revoked_at,
                replaced_by_token_id=token.replaced_by_token_id,
                created_at=token.created_at,
            )
            self._session.add(model)
        else:
            existing.revoked_at = token.revoked_at
            existing.replaced_by_token_id = token.replaced_by_token_id
            existing.expires_at = token.expires_at
            model = existing

        await self._session.commit()
        return self._to_domain(model)

    async def revoke_all_for_user(self, user_id: UUID) -> int:
        now = datetime.now(UTC)
        stmt = (
            select(RefreshTokenModel)
            .where(
                RefreshTokenModel.user_id == user_id,
                RefreshTokenModel.revoked_at.is_(None),
            )
            .execution_options(populate_existing=True)
        )
        result = await self._session.execute(stmt)
        models = result.scalars().all()
        for m in models:
            m.revoked_at = now
        await self._session.commit()
        return len(models)

