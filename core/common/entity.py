from dataclasses import dataclass, field
from typing import Any
from uuid import UUID

from uuid_utils import uuid7


@dataclass
class Entity:
    id: UUID = field(init=False, default_factory=lambda: uuid7())

    def __eq__(self, other: Any) -> bool:
        if isinstance(other, type(self)):
            return self.id == other.id
        return False

    def __hash__(self):
        return hash(self.id)


class AggregateRoot(Entity):
    pass
