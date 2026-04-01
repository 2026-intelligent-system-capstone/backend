from dataclasses import dataclass
from enum import StrEnum

from core.common.entity import Entity
from core.common.value_object import ValueObject


class OrganizationAuthProvider(ValueObject, StrEnum):
    HANSUNG_SIS = "hansung_sis"


@dataclass
class Organization(Entity):
    code: str
    name: str
    auth_provider: OrganizationAuthProvider
    is_active: bool = True

    @property
    def is_deleted(self) -> bool:
        return not self.is_active

    def needs_code_change(self, code: str) -> bool:
        return code != self.code

    def update(
        self,
        *,
        code: str | None = None,
        name: str | None = None,
        auth_provider: OrganizationAuthProvider | None = None,
        is_active: bool | None = None,
    ) -> None:
        if code is not None:
            self.code = code
        if name is not None:
            self.name = name
        if auth_provider is not None:
            self.auth_provider = auth_provider
        if is_active is not None:
            self.is_active = is_active

    def delete(self) -> None:
        self.is_active = False
