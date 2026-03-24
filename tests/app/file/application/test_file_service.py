from uuid import UUID

import pytest

from app.file.application.exception import FileNotFoundException
from app.file.application.service.file import FileService
from app.file.domain.command import CreateFileCommand, UpdateFileCommand
from app.file.domain.entity.file import File, FileStatus
from app.file.domain.repository.file import FileRepository


class InMemoryFileRepository(FileRepository):
    def __init__(self):
        self.files: dict[UUID, File] = {}

    async def save(self, entity: File) -> File:
        self.files[entity.id] = entity
        return entity

    async def get_by_id(self, entity_id: UUID) -> File | None:
        file = self.files.get(entity_id)
        if file is None or file.status == FileStatus.DELETED:
            return None
        return file

    async def list(self) -> list[File]:
        return [
            file
            for file in self.files.values()
            if file.status != FileStatus.DELETED
        ]


def make_create_command() -> CreateFileCommand:
    return CreateFileCommand(
        file_name="avatar.png",
        file_path="uploads/avatar.png",
        file_extension="png",
        file_size=1024,
        mime_type="image/png",
    )


@pytest.mark.asyncio
async def test_create_file_success():
    repo = InMemoryFileRepository()
    service = FileService(repository=repo)

    file = await service.create_file(make_create_command())

    assert file.file_name == "avatar.png"
    assert file.status == FileStatus.PENDING


@pytest.mark.asyncio
async def test_get_file_not_found():
    repo = InMemoryFileRepository()
    service = FileService(repository=repo)

    with pytest.raises(FileNotFoundException):
        await service.get_file(UUID("00000000-0000-0000-0000-000000000000"))


@pytest.mark.asyncio
async def test_update_file_success():
    repo = InMemoryFileRepository()
    service = FileService(repository=repo)
    created_file = await service.create_file(make_create_command())

    updated_file = await service.update_file(
        created_file.id,
        UpdateFileCommand(
            file_name="resume.pdf",
            mime_type="application/pdf",
            status=FileStatus.ACTIVE,
        ),
    )

    assert updated_file.file_name == "resume.pdf"
    assert updated_file.mime_type == "application/pdf"
    assert updated_file.status == FileStatus.ACTIVE


@pytest.mark.asyncio
async def test_update_file_omitted_fields_keep_existing_values():
    repo = InMemoryFileRepository()
    service = FileService(repository=repo)
    created_file = await service.create_file(make_create_command())

    updated_file = await service.update_file(
        created_file.id,
        UpdateFileCommand(file_name="renamed.png"),
    )

    assert updated_file.file_name == "renamed.png"
    assert updated_file.file_path == "uploads/avatar.png"
    assert updated_file.status == FileStatus.PENDING


@pytest.mark.asyncio
async def test_delete_file_excludes_from_list():
    repo = InMemoryFileRepository()
    service = FileService(repository=repo)
    created_file = await service.create_file(make_create_command())

    deleted_file = await service.delete_file(created_file.id)
    listed_files = await service.list_files()

    assert deleted_file.status == FileStatus.DELETED
    assert listed_files == []
