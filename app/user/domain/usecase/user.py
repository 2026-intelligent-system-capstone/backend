from abc import ABC, abstractmethod
from uuid import UUID

from app.user.domain.command import CreateUserCommand, UpdateUserCommand
from app.user.domain.entity.user import User


class UserUseCase(ABC):
    @abstractmethod
    async def create_user(self, command: CreateUserCommand) -> User:
        """Create user."""

    @abstractmethod
    async def get_user(self, user_id: UUID) -> User:
        """Get user."""

    @abstractmethod
    async def list_users(self) -> list[User]:
        """List users."""

    @abstractmethod
    async def update_user(
        self, user_id: UUID, command: UpdateUserCommand
    ) -> User:
        """Update user."""

    @abstractmethod
    async def delete_user(self, user_id: UUID) -> User:
        """Delete user."""
