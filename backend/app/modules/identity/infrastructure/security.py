"""Password hashing (bcrypt) and JWT token service (PyJWT) for Identity infrastructure."""

import hashlib
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
import secrets
from typing import Any
from uuid import UUID, uuid4

import bcrypt
import jwt

from app.core.config import Settings, get_settings
from app.modules.identity.domain.entities import UserRole
from app.modules.identity.domain.exceptions import InvalidCredentialsError
from app.modules.identity.domain.repositories import PasswordHasher, TokenProvider


def hash_token(raw_token: str) -> str:
    """Returns SHA-256 hex digest of a raw token string."""
    return hashlib.sha256(raw_token.strip().encode("utf-8")).hexdigest()



@dataclass(frozen=True, kw_only=True)
class DecodedTokenPayload:
    """Validated JWT claims extracted from an access or refresh token."""

    user_id: UUID
    email: str | None
    roles: frozenset[UserRole]
    token_type: str


class BcryptPasswordHasher(PasswordHasher):
    """Hashes and verifies passwords using direct bcrypt (compatible with Python 3.12+)."""

    def hash_password(self, plain_password: str) -> str:
        salt = bcrypt.gensalt()
        hashed: bytes = bcrypt.hashpw(plain_password.encode("utf-8"), salt)
        return hashed.decode("utf-8")

    def verify_password(self, plain_password: str, password_hash: str) -> bool:
        try:
            return bcrypt.checkpw(
                plain_password.encode("utf-8"),
                password_hash.encode("utf-8"),
            )
        except ValueError:
            return False


class JwtTokenService(TokenProvider):
    """Issues and validates signed JWT access and refresh tokens."""

    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings or get_settings()

    def create_access_token(
        self,
        user_id: UUID,
        email: str,
        roles: set[UserRole],
    ) -> str:
        now = datetime.now(UTC)
        expire = now + timedelta(minutes=self._settings.jwt_access_token_expire_minutes)
        payload: dict[str, Any] = {
            "sub": str(user_id),
            "email": email,
            "roles": sorted(role.value for role in roles),
            "type": "access",
            "iat": int(now.timestamp()),
            "exp": int(expire.timestamp()),
        }
        return jwt.encode(
            payload,
            self._settings.jwt_secret_key,
            algorithm=self._settings.jwt_algorithm,
        )

    def create_refresh_token(self, user_id: UUID) -> str:
        now = datetime.now(UTC)
        expire = now + timedelta(days=self._settings.jwt_refresh_token_expire_days)
        payload: dict[str, Any] = {
            "sub": str(user_id),
            "jti": str(uuid4()),
            "type": "refresh",
            "iat": int(now.timestamp()),
            "exp": int(expire.timestamp()),
        }
        return jwt.encode(
            payload,
            self._settings.jwt_secret_key,
            algorithm=self._settings.jwt_algorithm,
        )

    def decode_access_token(self, token: str) -> DecodedTokenPayload:
        try:
            payload = jwt.decode(
                token,
                self._settings.jwt_secret_key,
                algorithms=[self._settings.jwt_algorithm],
            )
        except jwt.PyJWTError as exc:
            raise InvalidCredentialsError() from exc

        token_type = payload.get("type")
        sub = payload.get("sub")
        if token_type != "access" or not isinstance(sub, str):
            raise InvalidCredentialsError()

        raw_roles = payload.get("roles", [])
        try:
            user_id = UUID(sub)
            roles = frozenset(UserRole(r) for r in raw_roles)
        except ValueError as exc:
            raise InvalidCredentialsError() from exc

        return DecodedTokenPayload(
            user_id=user_id,
            email=payload.get("email"),
            roles=roles,
            token_type=token_type,
        )
