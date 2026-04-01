from pathlib import Path
from uuid import UUID

from app.file.application.exception import (
    FileNotFoundException,
    FileUploadFailedException,
)
from app.file.domain.command import CreateFileCommand, UpdateFileCommand
from app.file.domain.entity.file import File, FileStatus
from app.file.domain.entity.file_download import FileDownload
from app.file.domain.repository.file import FileRepository
from app.file.domain.service import FileStorage, FileUploadData
from app.file.domain.usecase.file import FileUseCase
from core.db.transactional import transactional


class FileService(FileUseCase):
    def __init__(self, *, repository: FileRepository, storage: FileStorage):
        self.repository = repository
        self.storage = storage

    @transactional
    async def create_file(self, command: CreateFileCommand) -> File:
        file = File(
            file_name=command.file_name,
            file_path=command.file_path,
            file_extension=command.file_extension,
            file_size=command.file_size,
            mime_type=command.mime_type,
        )
        await self.repository.save(file)
        return file

    @transactional
    async def upload_file(
        self,
        *,
        file_upload: FileUploadData,
        directory: str,
        status: FileStatus = FileStatus.PENDING,
    ) -> File:
        try:
            stored_file = await self.storage.upload(
                file_upload=file_upload,
                directory=directory,
            )
        except Exception as exc:
            raise FileUploadFailedException() from exc

        file_extension = Path(file_upload.file_name).suffix.lstrip(".").lower()
        file = File(
            file_name=file_upload.file_name,
            file_path=stored_file.path,
            file_extension=file_extension,
            file_size=stored_file.size,
            mime_type=file_upload.mime_type,
            status=status,
        )
        await self.repository.save(file)
        return file

    async def list_files(self) -> list[File]:
        return list(await self.repository.list())

    async def get_file(self, file_id: UUID) -> File:
        file = await self.repository.get_by_id(file_id)
        if file is None:
            raise FileNotFoundException()
        return file

    async def get_file_download(self, file_id: UUID) -> FileDownload:
        file = await self.get_file(file_id)
        stored_file = await self.storage.open(path=file.file_path)
        return FileDownload(file=file, content=stored_file.content)

    @transactional
    async def update_file(
        self, file_id: UUID, command: UpdateFileCommand
    ) -> File:
        file = await self.get_file(file_id)
        delivered_fields = command.model_fields_set

        file.update(
            file_name=(
                command.file_name
                if "file_name" in delivered_fields
                else None
            ),
            file_path=(
                command.file_path
                if "file_path" in delivered_fields
                else None
            ),
            file_extension=(
                command.file_extension
                if "file_extension" in delivered_fields
                else None
            ),
            file_size=(
                command.file_size
                if "file_size" in delivered_fields
                else None
            ),
            mime_type=(
                command.mime_type
                if "mime_type" in delivered_fields
                else None
            ),
            status=(
                command.status if "status" in delivered_fields else None
            ),
        )

        await self.repository.save(file)
        return file

    @transactional
    async def delete_file(self, file_id: UUID) -> File:
        file = await self.get_file(file_id)
        should_remove_from_storage = file.delete()
        if should_remove_from_storage:
            await self.storage.delete(path=file.file_path)
        await self.repository.save(file)
        return file
