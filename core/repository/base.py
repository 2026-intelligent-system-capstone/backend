from abc import ABC, abstractmethod
from collections.abc import Sequence
from uuid import UUID

from core.common.entity import Entity


class BaseRepository[T: Entity](ABC):
    @abstractmethod
    async def save(self, entity: T) -> T:
        pass

    @abstractmethod
    async def get_by_id(self, entity_id: UUID) -> T | None:
        pass

    @abstractmethod
    async def list(self) -> Sequence[T]:
        pass

    @abstractmethod
    async def delete(self, entity: T) -> None:
        pass
