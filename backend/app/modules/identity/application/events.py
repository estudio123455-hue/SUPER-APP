"""Domain events emitted by the Identity bounded context."""

from dataclasses import dataclass
from uuid import UUID

from app.core.event_bus import DomainEvent


@dataclass(frozen=True, kw_only=True)
class UserRegisteredEvent(DomainEvent):
    """Published to EventBus whenever a new user registers in the Super App."""

    user_id: UUID
    email: str
    full_name: str
    roles: tuple[str, ...]
