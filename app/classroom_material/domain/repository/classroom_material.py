from abc import abstractmethod
from collections.abc import Sequence
from uuid import UUID

from app.classroom_material.domain.entity import ClassroomMaterial
from core.repository.base import BaseRepository


class ClassroomMaterialRepository(BaseRepository[ClassroomMaterial]):
    @abstractmethod
    async def list_by_classroom(
        self,
        classroom_id: UUID,
    ) -> Sequence[ClassroomMaterial]:
        pass

    @abstractmethod
    async def delete(self, entity: ClassroomMaterial) -> None:
        pass
