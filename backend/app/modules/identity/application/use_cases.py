"""Application Use Cases for the Identity module (Layer 2)."""

from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from app.core.config import get_settings
from app.core.event_bus import InMemoryEventBus
from app.modules.identity.application.dtos import (
    AuthenticateUserCommand,
    AuthTokensDTO,
    RegisterUserCommand,
    RevokeRefreshTokenCommand,
    RotateRefreshTokenCommand,
    UserDTO,
)
from app.modules.identity.application.events import UserRegisteredEvent
from app.modules.identity.domain.entities import RefreshToken, User, UserRole
from app.modules.identity.domain.exceptions import (
    InactiveUserError,
    InvalidCredentialsError,
    InvalidRefreshTokenError,
    RevokedRefreshTokenError,
    UserAlreadyExistsError,
    UserNotFoundError,
)
from app.modules.identity.domain.repositories import (
    PasswordHasher,
    RefreshTokenRepository,
    TokenProvider,
    UserRepository,
)
from app.modules.identity.infrastructure.security import hash_token



class RegisterUserUseCase:
    """Orchestrates new user registration and publishes UserRegisteredEvent."""

    def __init__(
        self,
        repository: UserRepository,
        password_hasher: PasswordHasher,
        event_bus: InMemoryEventBus,
    ) -> None:
        self._repository = repository
        self._password_hasher = password_hasher
        self._event_bus = event_bus

    async def execute(self, command: RegisterUserCommand) -> UserDTO:
        normalized_email = command.email.strip().lower()
        existing = await self._repository.get_by_email(normalized_email)
        if existing is not None:
            raise UserAlreadyExistsError(normalized_email)

        roles = frozenset(command.roles) if command.roles else frozenset({UserRole.USER})
        user = User(
            email=normalized_email,
            password_hash=self._password_hasher.hash_password(command.password),
            full_name=command.full_name.strip(),
            roles=roles,
        )

        saved_user = await self._repository.save(user)

        await self._event_bus.publish(
            UserRegisteredEvent(
                user_id=saved_user.id,
                email=saved_user.email,
                full_name=saved_user.full_name,
                roles=tuple(sorted(r.value for r in saved_user.roles)),
            )
        )

        return UserDTO.from_entity(saved_user)


class AuthenticateUserUseCase:
    """Verifies user credentials and issues access_token and refresh_token."""

    def __init__(
        self,
        repository: UserRepository,
        password_hasher: PasswordHasher,
        token_provider: TokenProvider,
        refresh_token_repository: RefreshTokenRepository | None = None,
    ) -> None:
        self._repository = repository
        self._password_hasher = password_hasher
        self._token_provider = token_provider
        self._refresh_token_repository = refresh_token_repository

    async def execute(self, command: AuthenticateUserCommand) -> AuthTokensDTO:
        normalized_email = command.email.strip().lower()
        user = await self._repository.get_by_email(normalized_email)
        if user is None:
            raise InvalidCredentialsError()

        if not self._password_hasher.verify_password(
            command.password, user.password_hash
        ):
            raise InvalidCredentialsError()

        if not user.is_active:
            raise InactiveUserError(str(user.id))

        access_token = self._token_provider.create_access_token(
            user_id=user.id,
            email=user.email,
            roles=set(user.roles),
        )
        refresh_token = self._token_provider.create_refresh_token(user_id=user.id)

        if self._refresh_token_repository is not None:
            settings = get_settings()
            expires_at = datetime.now(UTC) + timedelta(
                days=settings.jwt_refresh_token_expire_days
            )
            token_entity = RefreshToken(
                user_id=user.id,
                token_hash=hash_token(refresh_token),
                expires_at=expires_at,
            )
            await self._refresh_token_repository.save(token_entity)

        return AuthTokensDTO(
            access_token=access_token,
            refresh_token=refresh_token,
        )


class RotateRefreshTokenUseCase:
    """Validates an incoming refresh token, rotates it with revocations and issues new tokens."""

    def __init__(
        self,
        user_repository: UserRepository,
        refresh_token_repository: RefreshTokenRepository,
        token_provider: TokenProvider,
    ) -> None:
        self._user_repository = user_repository
        self._refresh_token_repository = refresh_token_repository
        self._token_provider = token_provider

    async def execute(self, command: RotateRefreshTokenCommand) -> AuthTokensDTO:
        raw_token = command.refresh_token.strip()
        if not raw_token:
            raise InvalidRefreshTokenError("Refresh token must not be empty.")

        token_hash = hash_token(raw_token)
        token_record = await self._refresh_token_repository.get_by_hash(token_hash)
        if token_record is None:
            raise InvalidRefreshTokenError("Refresh token was not found or is invalid.")

        if token_record.revoked_at is not None:
            # Replay/Theft detection: revoke all active tokens for this user
            await self._refresh_token_repository.revoke_all_for_user(token_record.user_id)
            raise RevokedRefreshTokenError(
                "Refresh token has already been revoked. Potential token reuse detected."
            )

        now = datetime.now(UTC)
        if not token_record.is_valid(now):
            raise InvalidRefreshTokenError("Refresh token has expired.")

        user = await self._user_repository.get_by_id(token_record.user_id)
        if user is None:
            raise UserNotFoundError(str(token_record.user_id))
        if not user.is_active:
            raise InactiveUserError(str(user.id))

        new_access_token = self._token_provider.create_access_token(
            user_id=user.id,
            email=user.email,
            roles=set(user.roles),
        )
        new_refresh_token = self._token_provider.create_refresh_token(user_id=user.id)
        new_token_id = uuid4()
        new_token_hash = hash_token(new_refresh_token)
        settings = get_settings()
        new_expires_at = now + timedelta(days=settings.jwt_refresh_token_expire_days)

        new_token_entity = RefreshToken(
            id=new_token_id,
            user_id=user.id,
            token_hash=new_token_hash,
            expires_at=new_expires_at,
        )

        revoked_old = token_record.revoke(replaced_by=new_token_id, now=now)

        await self._refresh_token_repository.save(new_token_entity)
        await self._refresh_token_repository.save(revoked_old)

        return AuthTokensDTO(
            access_token=new_access_token,
            refresh_token=new_refresh_token,
        )


class RevokeRefreshTokenUseCase:
    """Revokes an active refresh token upon user logout."""

    def __init__(
        self,
        refresh_token_repository: RefreshTokenRepository,
    ) -> None:
        self._refresh_token_repository = refresh_token_repository

    async def execute(self, command: RevokeRefreshTokenCommand) -> bool:
        raw_token = command.refresh_token.strip()
        if not raw_token:
            return False

        token_hash = hash_token(raw_token)
        token_record = await self._refresh_token_repository.get_by_hash(token_hash)
        if token_record is None or token_record.revoked_at is not None:
            return True

        revoked = token_record.revoke()
        await self._refresh_token_repository.save(revoked)
        return True



class GetUserProfileUseCase:
    """Retrieves an active user's profile by UUID."""

    def __init__(self, repository: UserRepository) -> None:
        self._repository = repository

    async def execute(self, user_id: UUID) -> UserDTO:
        user = await self._repository.get_by_id(user_id)
        if user is None:
            raise UserNotFoundError(str(user_id))
        if not user.is_active:
            raise InactiveUserError(str(user.id))
        return UserDTO.from_entity(user)
