"""FastAPI router for the Identity bounded context (/api/v1/identity)."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db_session
from app.core.event_bus import event_bus
from app.modules.identity.application.dtos import (
    AuthenticateUserCommand,
    RegisterUserCommand,
    RevokeRefreshTokenCommand,
    RotateRefreshTokenCommand,
)
from app.modules.identity.application.use_cases import (
    AuthenticateUserUseCase,
    RegisterUserUseCase,
    RevokeRefreshTokenUseCase,
    RotateRefreshTokenUseCase,
)
from app.modules.identity.domain.entities import UserRole
from app.modules.identity.domain.exceptions import (
    InactiveUserError,
    InvalidCredentialsError,
    InvalidRefreshTokenError,
    RevokedRefreshTokenError,
    UserAlreadyExistsError,
    UserNotFoundError,
)
from app.modules.identity.infrastructure.repositories import (
    SqlAlchemyRefreshTokenRepository,
    SqlAlchemyUserRepository,
)
from app.modules.identity.infrastructure.security import (
    BcryptPasswordHasher,
    JwtTokenService,
)
from app.modules.identity.presentation.schemas import (
    LoginRequest,
    LogoutRequest,
    LogoutResponse,
    RefreshTokenRequest,
    RegisterUserRequest,
    TokenPairResponse,
    UserResponse,
)
from app.modules.identity.public_api import UserPublicDTO, get_current_user


router = APIRouter(prefix="/api/v1/identity", tags=["Identity"])


@router.post(
    "/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
)
async def register_user(
    payload: RegisterUserRequest,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> UserResponse:
    """Registers a new user account and emits UserRegisteredEvent."""
    repository = SqlAlchemyUserRepository(session)
    hasher = BcryptPasswordHasher()
    use_case = RegisterUserUseCase(
        repository=repository,
        password_hasher=hasher,
        event_bus=event_bus,
    )

    try:
        user_dto = await use_case.execute(
            RegisterUserCommand(
                email=payload.email,
                password=payload.password,
                full_name=payload.full_name,
                roles=set(payload.roles),
            )
        )
    except UserAlreadyExistsError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc

    return UserResponse(
        id=user_dto.id,
        email=user_dto.email,
        full_name=user_dto.full_name,
        roles=sorted(user_dto.roles, key=lambda r: r.value),
        is_active=user_dto.is_active,
        created_at=user_dto.created_at,
    )


@router.post(
    "/login",
    response_model=TokenPairResponse,
    status_code=status.HTTP_200_OK,
)
@router.post(
    "/auth/login",
    response_model=TokenPairResponse,
    status_code=status.HTTP_200_OK,
    include_in_schema=True,
)
async def login_user(
    payload: LoginRequest,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> TokenPairResponse:
    """Authenticates a user and returns JWT access and rotatable refresh tokens."""
    repository = SqlAlchemyUserRepository(session)
    refresh_repo = SqlAlchemyRefreshTokenRepository(session)
    hasher = BcryptPasswordHasher()
    token_service = JwtTokenService()
    use_case = AuthenticateUserUseCase(
        repository=repository,
        password_hasher=hasher,
        token_provider=token_service,
        refresh_token_repository=refresh_repo,
    )

    try:
        tokens = await use_case.execute(
            AuthenticateUserCommand(
                email=payload.email,
                password=payload.password,
            )
        )
    except InvalidCredentialsError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(exc),
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc
    except InactiveUserError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(exc),
        ) from exc

    return TokenPairResponse(
        access_token=tokens.access_token,
        refresh_token=tokens.refresh_token,
        token_type=tokens.token_type,
    )


@router.post(
    "/refresh",
    response_model=TokenPairResponse,
    status_code=status.HTTP_200_OK,
)
@router.post(
    "/auth/refresh",
    response_model=TokenPairResponse,
    status_code=status.HTTP_200_OK,
    include_in_schema=True,
)
async def refresh_tokens(
    payload: RefreshTokenRequest,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> TokenPairResponse:
    """Rotates an existing refresh token, invalidates old token, and issues a new pair."""
    user_repo = SqlAlchemyUserRepository(session)
    refresh_repo = SqlAlchemyRefreshTokenRepository(session)
    token_service = JwtTokenService()
    use_case = RotateRefreshTokenUseCase(
        user_repository=user_repo,
        refresh_token_repository=refresh_repo,
        token_provider=token_service,
    )

    try:
        tokens = await use_case.execute(
            RotateRefreshTokenCommand(refresh_token=payload.refresh_token)
        )
    except RevokedRefreshTokenError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(exc),
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc
    except InvalidRefreshTokenError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(exc),
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc
    except InactiveUserError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(exc),
        ) from exc
    except UserNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc

    return TokenPairResponse(
        access_token=tokens.access_token,
        refresh_token=tokens.refresh_token,
        token_type=tokens.token_type,
    )


@router.post(
    "/logout",
    response_model=LogoutResponse,
    status_code=status.HTTP_200_OK,
)
@router.post(
    "/auth/logout",
    response_model=LogoutResponse,
    status_code=status.HTTP_200_OK,
    include_in_schema=True,
)
async def logout_user(
    payload: LogoutRequest,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> LogoutResponse:
    """Revokes a refresh token upon user logout."""
    refresh_repo = SqlAlchemyRefreshTokenRepository(session)
    use_case = RevokeRefreshTokenUseCase(refresh_token_repository=refresh_repo)
    await use_case.execute(
        RevokeRefreshTokenCommand(refresh_token=payload.refresh_token)
    )
    return LogoutResponse()



@router.get(
    "/me",
    response_model=UserResponse,
    status_code=status.HTTP_200_OK,
)
async def get_me(
    current_user: Annotated[UserPublicDTO, Depends(get_current_user)],
) -> UserResponse:
    """Returns the currently authenticated user's profile."""
    return UserResponse(
        id=current_user.id,
        email=current_user.email,
        full_name=current_user.full_name,
        roles=sorted((UserRole(r) for r in current_user.roles), key=lambda r: r.value),
        is_active=current_user.is_active,
        created_at=current_user.created_at,
    )
