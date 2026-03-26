from dataclasses import dataclass
from enum import StrEnum
from uuid import UUID

from core.common.entity import Entity
from core.common.value_object import ValueObject


class UserStatus(ValueObject, StrEnum):
    ACTIVE = "active"
    PENDING = "pending"
    BLOCKED = "blocked"


class UserRole(ValueObject, StrEnum):
    STUDENT = "student"
    PROFESSOR = "professor"
    ADMIN = "admin"


@dataclass
class User(Entity):
    organization_id: UUID
    login_id: str
    role: UserRole
    email: str | None
    name: str
    status: UserStatus = UserStatus.ACTIVE
    is_deleted: bool = False

    def delete(self) -> None:
        self.is_deleted = True
