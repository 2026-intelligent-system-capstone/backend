from dataclasses import dataclass
from enum import StrEnum

from core.common.entity import Entity
from core.common.value_object import ValueObject


class FileStatus(ValueObject, StrEnum):
    PENDING = "pending"  # Uploaded to storage but not yet linked/confirmed
    ACTIVE = "active"  # Linked to another domain record
    DELETED = "deleted"


@dataclass
class File(Entity):
    file_name: str
    file_path: str  # Storage path or key
    file_extension: str
    file_size: int  # in bytes
    mime_type: str
    status: FileStatus = FileStatus.PENDING

    def activate(self) -> None:
        self.status = FileStatus.ACTIVE

    def delete(self) -> None:
        self.status = FileStatus.DELETED
