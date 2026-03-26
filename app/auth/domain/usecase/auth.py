from abc import ABC, abstractmethod

from app.auth.domain.command import (
    LoginCommand,
    LogoutCommand,
    RefreshTokenCommand,
)
from app.auth.domain.entity import AuthTokens


class AuthUseCase(ABC):
    @abstractmethod
    async def login(self, command: LoginCommand) -> AuthTokens:
        """Login user and issue tokens."""

    @abstractmethod
    async def refresh(self, command: RefreshTokenCommand) -> AuthTokens:
        """Refresh tokens."""

    @abstractmethod
    async def logout(self, command: LogoutCommand) -> None:
        """Logout current session."""
