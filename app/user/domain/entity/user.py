from dataclasses import dataclass
from enum import StrEnum
from uuid import UUID

from core.common.entity import Entity
from core.common.value_object import ValueObject


class UserStatus(ValueObject, StrEnum):
    ACTIVE = "active"
    PENDING = "pending"
    BLOCKED = "blocked"


@dataclass
class Profile(ValueObject):
    nickname: str
    real_name: str
    phone_number: str | None = None
    profile_image_id: UUID | None = None

    def __composite_values__(self) -> tuple[str, str, str | None, UUID | None]:
        return (
            self.nickname,
            self.real_name,
            self.phone_number,
            self.profile_image_id,
        )


@dataclass
class User(Entity):
    username: str
    password: str
    email: str
    profile: Profile
    status: UserStatus = UserStatus.ACTIVE
    is_deleted: bool = False

    def update_profile(self, new_profile: Profile) -> None:
        self.profile = new_profile

    def delete(self) -> None:
        self.is_deleted = True
