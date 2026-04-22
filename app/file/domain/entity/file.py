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

    def update(
        self,
        *,
        file_name: str | None = None,
        file_path: str | None = None,
        file_extension: str | None = None,
        file_size: int | None = None,
        mime_type: str | None = None,
        status: FileStatus | None = None,
    ) -> None:
        if file_name is not None:
            self.file_name = file_name
        if file_path is not None:
            self.file_path = file_path
        if file_extension is not None:
            self.file_extension = file_extension
        if file_size is not None:
            self.file_size = file_size
        if mime_type is not None:
            self.mime_type = mime_type
        if status is not None:
            self.status = status

    def activate(self) -> None:
        self.status = FileStatus.ACTIVE

    def delete(self) -> bool:
        should_remove_from_storage = self.status != FileStatus.DELETED
        self.status = FileStatus.DELETED
        return should_remove_from_storage
