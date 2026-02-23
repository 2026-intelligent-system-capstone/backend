from abc import ABC, abstractmethod
from typing import Generic, TypeVar, Sequence
from uuid import UUID
from core.common.entity import Entity

T = TypeVar("T", bound=Entity)

class BaseRepository(Generic[T], ABC):
    @abstractmethod
    async def save(self, entity: T) -> T:
        """Save an entity."""
        pass

    @abstractmethod
    async def get_by_id(self, id: UUID) -> T | None:
        """Get an entity by its UUID."""
        pass

    @abstractmethod
    async def list(self) -> Sequence[T]:
        """List all entities."""
        pass

    @abstractmethod
    async def delete(self, entity: T) -> None:
        """Delete an entity."""
        pass
