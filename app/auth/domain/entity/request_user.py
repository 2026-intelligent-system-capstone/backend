from dataclasses import dataclass
from uuid import UUID

from starlette.authentication import BaseUser


@dataclass(frozen=True)
class RequestUser(BaseUser):
    id: UUID | None = None

    @property
    def is_authenticated(self) -> bool:
        return self.id is not None

    @property
    def display_name(self) -> str:
        return str(self.id) if self.id is not None else "anonymous"
