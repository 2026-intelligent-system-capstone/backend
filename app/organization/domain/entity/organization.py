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
