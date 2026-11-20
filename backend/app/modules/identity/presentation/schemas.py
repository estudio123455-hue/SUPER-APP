"""Pydantic v2 request and response schemas for the Identity presentation layer."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.modules.identity.domain.entities import UserRole


class RegisterUserRequest(BaseModel):
    """Payload for registering a new user account."""

    model_config = ConfigDict(from_attributes=True)

    email: str = Field(..., min_length=5, max_length=255, examples=["creator@superapp.io"])
    password: str = Field(..., min_length=8, max_length=128)
    full_name: str = Field(..., min_length=2, max_length=255, examples=["Ada Lovelace"])
    roles: list[UserRole] = Field(default_factory=lambda: [UserRole.USER])


class LoginRequest(BaseModel):
    """Payload for authenticating a user with email and password."""

    model_config = ConfigDict(from_attributes=True)

    email: str = Field(..., min_length=5, max_length=255)
    password: str = Field(..., min_length=1, max_length=128)


class TokenPairResponse(BaseModel):
    """JWT access and refresh token response."""

    model_config = ConfigDict(from_attributes=True)

    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class RefreshTokenRequest(BaseModel):
    """Payload for rotating an existing refresh token."""

    model_config = ConfigDict(from_attributes=True)

    refresh_token: str = Field(..., min_length=10)


class LogoutRequest(BaseModel):
    """Payload for revoking a refresh token upon user logout."""

    model_config = ConfigDict(from_attributes=True)

    refresh_token: str = Field(..., min_length=10)


class LogoutResponse(BaseModel):
    """Confirmation message returned upon successful logout."""

    model_config = ConfigDict(from_attributes=True)

    status: str = "logged_out"
    message: str = "Successfully logged out"



class UserResponse(BaseModel):
    """Public profile representation returned by the Identity API."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    email: str
    full_name: str
    roles: list[UserRole]
    is_active: bool
    created_at: datetime
