from abc import abstractmethod
from collections.abc import Sequence
from uuid import UUID

from app.classroom.domain.entity import Classroom
from core.repository.base import BaseRepository


class ClassroomRepository(BaseRepository[Classroom]):
    @abstractmethod
    async def get_by_organization_and_name_and_term(
        self,
        organization_id: UUID,
        name: str,
        grade: int,
        semester: str,
        section: str,
    ) -> Classroom | None:
        pass

    @abstractmethod
    async def list_by_organization(
        self,
        organization_id: UUID,
    ) -> Sequence[Classroom]:
        pass

    @abstractmethod
    async def delete(self, entity: Classroom) -> None:
        pass
