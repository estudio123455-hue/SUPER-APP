"""Internal and cross-layer DTOs for the Identity application layer."""

from dataclasses import dataclass, field
from datetime import datetime
from uuid import UUID

from app.modules.identity.domain.entities import User, UserRole


@dataclass(frozen=True, kw_only=True)
class RegisterUserCommand:
    """Input command for registering a new user."""

    email: str
    password: str
    full_name: str
    roles: set[UserRole] = field(default_factory=lambda: {UserRole.USER})


@dataclass(frozen=True, kw_only=True)
class AuthenticateUserCommand:
    """Input command for authenticating an existing user."""

    email: str
    password: str


@dataclass(frozen=True, kw_only=True)
class RotateRefreshTokenCommand:
    """Input command for rotating a refresh token."""

    refresh_token: str


@dataclass(frozen=True, kw_only=True)
class RevokeRefreshTokenCommand:
    """Input command for revoking a refresh token upon logout."""

    refresh_token: str



@dataclass(frozen=True, kw_only=True)
class AuthTokensDTO:
    """Pair of JWT tokens returned upon successful authentication."""

    access_token: str
    refresh_token: str
    token_type: str = "bearer"


@dataclass(frozen=True, kw_only=True)
class UserDTO:
    """Safe representation of a User without sensitive password hash."""

    id: UUID
    email: str
    full_name: str
    roles: frozenset[UserRole]
    is_active: bool
    created_at: datetime

    @classmethod
    def from_entity(cls, user: User) -> "UserDTO":
        return cls(
            id=user.id,
            email=user.email,
            full_name=user.full_name,
            roles=user.roles,
            is_active=user.is_active,
            created_at=user.created_at,
        )
