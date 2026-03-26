from abc import abstractmethod

from app.organization.domain.entity import Organization
from core.repository.base import BaseRepository


class OrganizationRepository(BaseRepository[Organization]):
    @abstractmethod
    async def get_by_code(self, code: str) -> Organization | None:
        pass
