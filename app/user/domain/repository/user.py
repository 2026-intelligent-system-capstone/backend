from abc import abstractmethod

from app.user.domain.entity.user import User
from core.repository.base import BaseRepository


class UserRepository(BaseRepository[User]):
    @abstractmethod
    async def get_by_username(self, username: str) -> User | None:
        pass

    @abstractmethod
    async def get_by_email(self, email: str) -> User | None:
        pass
