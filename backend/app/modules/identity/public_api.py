"""Public API contract for the identity module (Law 1).

Other bounded contexts (media_ai, commerce, wallet) MUST ONLY import from this file
when they need to identify the authenticated user or subscribe to identity events.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db_session
from app.modules.identity.application.events import UserRegisteredEvent
from app.modules.identity.application.use_cases import GetUserProfileUseCase
from app.modules.identity.domain.exceptions import (
    InactiveUserError,
    InvalidCredentialsError,
    UserNotFoundError,
)
from app.modules.identity.infrastructure.repositories import SqlAlchemyUserRepository
from app.modules.identity.infrastructure.security import JwtTokenService

bearer_scheme = HTTPBearer(auto_error=False)


@dataclass(frozen=True, kw_only=True)
class UserPublicDTO:
    """Immutable cross-module contract representing an authenticated Super App user."""

    id: UUID
    email: str
    full_name: str
    roles: frozenset[str]
    is_active: bool
    created_at: datetime


async def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> UserPublicDTO:
    """FastAPI dependency resolving and verifying the current authenticated user."""
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or invalid Bearer authentication token.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token_service = JwtTokenService()
    try:
        decoded = token_service.decode_access_token(credentials.credentials)
        repository = SqlAlchemyUserRepository(session)
        use_case = GetUserProfileUseCase(repository)
        user_dto = await use_case.execute(decoded.user_id)
    except InvalidCredentialsError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(exc),
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc
    except UserNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authenticated user no longer exists.",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc
    except InactiveUserError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(exc),
        ) from exc

    return UserPublicDTO(
        id=user_dto.id,
        email=user_dto.email,
        full_name=user_dto.full_name,
        roles=frozenset(role.value for role in user_dto.roles),
        is_active=user_dto.is_active,
        created_at=user_dto.created_at,
    )


__all__ = ["UserPublicDTO", "UserRegisteredEvent", "get_current_user"]
