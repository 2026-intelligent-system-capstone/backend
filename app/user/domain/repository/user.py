from abc import abstractmethod
from collections.abc import Sequence
from uuid import UUID

from app.user.domain.entity import User
from core.repository.base import BaseRepository


class UserRepository(BaseRepository[User]):
    @abstractmethod
    async def get_by_organization_and_login_id(
        self,
        organization_id: UUID,
        login_id: str,
    ) -> User | None:
        pass

    @abstractmethod
    async def list_by_organization(
        self,
        organization_id: UUID,
    ) -> Sequence[User]:
        pass
