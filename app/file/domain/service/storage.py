from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import BinaryIO


@dataclass
class FileUploadData:
    file_name: str
    mime_type: str
    content: BinaryIO


@dataclass
class StoredFile:
    path: str
    size: int


@dataclass
class StoredFileContent:
    content: BinaryIO


class FileStorage(ABC):
    @abstractmethod
    async def upload(
        self,
        *,
        file_upload: FileUploadData,
        directory: str,
    ) -> StoredFile:
        """Upload a file and return storage metadata."""

    @abstractmethod
    async def delete(self, *, path: str) -> None:
        """Delete a file from storage."""

    @abstractmethod
    async def open(self, *, path: str) -> StoredFileContent:
        """Open a file from storage for reading."""
