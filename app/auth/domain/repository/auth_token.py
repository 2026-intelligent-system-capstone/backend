from abc import ABC, abstractmethod
from uuid import UUID


class AuthTokenRepository(ABC):
    @abstractmethod
    async def save(
        self,
        *,
        user_id: UUID,
        jti: str,
        refresh_token: str,
        expires_in: int,
    ) -> None:
        """Save refresh token."""

    @abstractmethod
    async def get(self, *, user_id: UUID, jti: str) -> str | None:
        """Get refresh token."""

    @abstractmethod
    async def delete(self, *, user_id: UUID, jti: str) -> None:
        """Delete refresh token."""
