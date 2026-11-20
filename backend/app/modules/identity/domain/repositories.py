"""Abstract repository & security contracts for the Identity domain (Law 3)."""

from typing import Protocol
from uuid import UUID

from app.modules.identity.domain.entities import RefreshToken, User, UserRole


class UserRepository(Protocol):
    """Port for persisting and retrieving User domain entities."""

    async def get_by_id(self, user_id: UUID) -> User | None:
        """Finds a user by their unique UUID."""
        ...

    async def get_by_email(self, email: str) -> User | None:
        """Finds a user by their normalized email address."""
        ...

    async def save(self, user: User) -> User:
        """Persists a new or updated User entity."""
        ...


class RefreshTokenRepository(Protocol):
    """Port for persisting and querying RefreshToken domain entities."""

    async def get_by_hash(self, token_hash: str) -> RefreshToken | None:
        """Finds an active or revoked refresh token by its SHA-256 hash."""
        ...

    async def get_by_id(self, token_id: UUID) -> RefreshToken | None:
        """Finds a refresh token by its primary UUID."""
        ...

    async def save(self, token: RefreshToken) -> RefreshToken:
        """Persists a new or updated RefreshToken entity."""
        ...

    async def revoke_all_for_user(self, user_id: UUID) -> int:
        """Revokes all active refresh tokens for a user (e.g., security breach)."""
        ...



class PasswordHasher(Protocol):
    """Port for hashing and verifying raw passwords."""

    def hash_password(self, plain_password: str) -> str:
        """Returns a secure hash of plain_password."""
        ...

    def verify_password(self, plain_password: str, password_hash: str) -> bool:
        """Verifies plain_password against password_hash."""
        ...


class TokenProvider(Protocol):
    """Port for issuing and decoding JWT access and refresh tokens."""

    def create_access_token(self, user_id: UUID, email: str, roles: set[UserRole]) -> str:
        """Creates a signed short-lived JWT access token."""
        ...

    def create_refresh_token(self, user_id: UUID) -> str:
        """Creates a signed long-lived JWT refresh token."""
        ...
