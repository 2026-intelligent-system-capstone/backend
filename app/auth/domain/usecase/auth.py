from abc import ABC, abstractmethod

from app.auth.application.dto import AuthTokensDTO
from app.auth.domain.command import (
    LoginCommand,
    LogoutCommand,
    RefreshTokenCommand,
)


class AuthUseCase(ABC):
    @abstractmethod
    async def login(self, command: LoginCommand) -> AuthTokensDTO:
        """Login user and issue tokens."""

    @abstractmethod
    async def refresh(self, command: RefreshTokenCommand) -> AuthTokensDTO:
        """Refresh tokens."""

    @abstractmethod
    async def logout(self, command: LogoutCommand) -> None:
        """Logout current session."""
