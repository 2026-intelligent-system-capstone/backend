from abc import abstractmethod
from uuid import UUID

from app.user.domain.entity.user import User
from core.repository.base import BaseRepository


class UserRepository(BaseRepository[User]):
    @abstractmethod
    async def get_by_organization_and_login_id(
        self,
        organization_id: UUID,
        login_id: str,
    ) -> User | None:
        pass
