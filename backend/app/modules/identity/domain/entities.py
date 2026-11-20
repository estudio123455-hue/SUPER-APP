"""Pure domain entities and value objects for the Identity bounded context (Law 3)."""

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from uuid import UUID, uuid4


class UserRole(StrEnum):
    """Supported roles across the Super App 4-year horizon."""

    USER = "USER"
    CREATOR = "CREATOR"
    MERCHANT = "MERCHANT"
    ADMIN = "ADMIN"


@dataclass(frozen=True, kw_only=True)
class User:
    """Immutable pure domain entity representing an account in the Super App."""

    id: UUID = field(default_factory=uuid4)
    email: str
    password_hash: str
    full_name: str
    roles: frozenset[UserRole] = field(
        default_factory=lambda: frozenset({UserRole.USER})
    )
    is_active: bool = True
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def __post_init__(self) -> None:
        normalized_email = self.email.strip().lower()
        if not normalized_email or "@" not in normalized_email:
            raise ValueError("Invalid email address format.")
        object.__setattr__(self, "email", normalized_email)
        if not isinstance(self.roles, frozenset):
            object.__setattr__(self, "roles", frozenset(self.roles))


@dataclass(frozen=True, kw_only=True)
class RefreshToken:
    """Immutable pure domain entity representing a persistent, rotatable refresh token."""

    id: UUID = field(default_factory=uuid4)
    user_id: UUID
    token_hash: str
    expires_at: datetime
    revoked_at: datetime | None = None
    replaced_by_token_id: UUID | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    @property
    def token_id(self) -> UUID:
        """Alias for id ensuring compatibility with token_id naming."""
        return self.id

    def is_valid(self, now: datetime | None = None) -> bool:
        """Returns True if the token is unrevoked and has not expired."""
        current_time = now or datetime.now(UTC)
        if self.expires_at.tzinfo is None and current_time.tzinfo is not None:
            current_time = current_time.replace(tzinfo=None)
        elif self.expires_at.tzinfo is not None and current_time.tzinfo is None:
            current_time = current_time.replace(tzinfo=UTC)
        return self.revoked_at is None and self.expires_at > current_time

    def revoke(
        self,
        replaced_by: UUID | None = None,
        now: datetime | None = None,
    ) -> "RefreshToken":
        """Returns a new immutable RefreshToken marked as revoked."""
        from dataclasses import replace

        current_time = now or datetime.now(UTC)
        return replace(
            self,
            revoked_at=current_time,
            replaced_by_token_id=replaced_by,
        )

