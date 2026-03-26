from abc import ABC, abstractmethod
from uuid import UUID

from app.file.domain.command import CreateFileCommand, UpdateFileCommand
from app.file.domain.entity.file import File, FileStatus
from app.file.domain.entity.file_download import FileDownload
from app.file.domain.service import FileUploadData


class FileUseCase(ABC):
    @abstractmethod
    async def create_file(self, command: CreateFileCommand) -> File:
        """Create file."""

    @abstractmethod
    async def upload_file(
        self,
        *,
        file_upload: FileUploadData,
        directory: str,
        status: FileStatus = FileStatus.PENDING,
    ) -> File:
        """Upload file content and persist metadata."""

    @abstractmethod
    async def get_file(self, file_id: UUID) -> File:
        """Get file."""

    @abstractmethod
    async def get_file_download(self, file_id: UUID) -> FileDownload:
        """Get file download content."""

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
