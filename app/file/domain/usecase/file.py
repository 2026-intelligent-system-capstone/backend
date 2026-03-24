from abc import ABC, abstractmethod
from uuid import UUID

from app.file.domain.command import CreateFileCommand, UpdateFileCommand
from app.file.domain.entity.file import File


class FileUseCase(ABC):
    @abstractmethod
    async def create_file(self, command: CreateFileCommand) -> File:
        """Create file."""

    @abstractmethod
    async def get_file(self, file_id: UUID) -> File:
        """Get file."""

    @abstractmethod
    async def list_files(self) -> list[File]:
        """List files."""

    @abstractmethod
    async def update_file(
        self, file_id: UUID, command: UpdateFileCommand
    ) -> File:
        """Update file."""

    @abstractmethod
    async def delete_file(self, file_id: UUID) -> File:
        """Delete file."""
