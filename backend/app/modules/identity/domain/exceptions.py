"""Pure domain exceptions for the Identity module (Law 3)."""


class IdentityDomainError(Exception):
    """Base domain exception for the Identity bounded context."""


class UserAlreadyExistsError(IdentityDomainError):
    """Raised when attempting to register an email that already exists."""

    def __init__(self, email: str) -> None:
        super().__init__(f"A user with email '{email}' already exists.")
        self.email = email


class InvalidCredentialsError(IdentityDomainError):
    """Raised when email or password verification fails."""

    def __init__(self) -> None:
        super().__init__("Invalid email or password.")


class InactiveUserError(IdentityDomainError):
    """Raised when an inactive or suspended user attempts an authenticated action."""

    def __init__(self, user_id: str) -> None:
        super().__init__(f"User account '{user_id}' is inactive.")
        self.user_id = user_id


class UserNotFoundError(IdentityDomainError):
    """Raised when a user cannot be found by ID or email."""

    def __init__(self, identifier: str) -> None:
        super().__init__(f"User '{identifier}' was not found.")
        self.identifier = identifier


class InvalidRefreshTokenError(IdentityDomainError):
    """Raised when a refresh token is expired, not found, or malformed."""

    def __init__(self, message: str = "Invalid or expired refresh token.") -> None:
        super().__init__(message)


class RevokedRefreshTokenError(IdentityDomainError):
    """Raised when an already revoked refresh token is presented (potential token theft/replay)."""

    def __init__(
        self,
        message: str = "Refresh token has been revoked. Potential token reuse detected.",
    ) -> None:
        super().__init__(message)

