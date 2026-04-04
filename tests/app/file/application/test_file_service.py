from io import BytesIO
from uuid import UUID

import pytest

from app.file.application.exception import (
    FileDeleteFailedException,
    FileDownloadFailedException,
    FileNotFoundException,
    FileUploadFailedException,
)
from app.file.application.service.file import FileService
from app.file.domain.command import CreateFileCommand, UpdateFileCommand
from app.file.domain.entity.file import File, FileStatus
from app.file.domain.repository.file import FileRepository
from app.file.domain.service import FileStorage, FileUploadData, StoredFile


class InMemoryFileRepository(FileRepository):
    def __init__(self):
        self.files: dict[UUID, File] = {}

    async def save(self, entity: File) -> None:
        self.files[entity.id] = entity

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


class FakeFileStorage(FileStorage):
    def __init__(self):
        self.upload_calls: list[tuple[str, str, bytes]] = []
        self.delete_calls: list[str] = []
        self.open_calls: list[str] = []
        self.contents_by_path: dict[str, bytes] = {}

    async def upload(
        self,
        *,
        file_upload: FileUploadData,
        directory: str,
    ) -> StoredFile:
        file_upload.content.seek(0)
        content = file_upload.content.read()
        self.upload_calls.append((directory, file_upload.file_name, content))
        path = f"{directory}/{file_upload.file_name}"
        self.contents_by_path[path] = content
        return StoredFile(
            path=path,
            size=len(content),
        )

    async def delete(self, *, path: str) -> None:
        self.delete_calls.append(path)

    async def open(self, *, path: str):
        self.open_calls.append(path)
        return type(
            "StoredContent",
            (),
            {"content": BytesIO(self.contents_by_path[path])},
        )()


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
    service = FileService(repository=repo, storage=FakeFileStorage())

    file = await service.create_file(make_create_command())

    assert file.file_name == "avatar.png"
    assert file.status == FileStatus.PENDING


@pytest.mark.asyncio
async def test_upload_file_success():
    repo = InMemoryFileRepository()
    storage = FakeFileStorage()
    service = FileService(repository=repo, storage=storage)

    file = await service.upload_file(
        file_upload=FileUploadData(
            file_name="week1.pdf",
            mime_type="application/pdf",
            content=BytesIO(b"pdf-content"),
        ),
        directory="classrooms/materials",
        status=FileStatus.ACTIVE,
    )

    assert file.file_name == "week1.pdf"
    assert file.file_path == "classrooms/materials/week1.pdf"
    assert file.file_extension == "pdf"
    assert file.file_size == 11
    assert file.status == FileStatus.ACTIVE
    assert storage.upload_calls == [
        ("classrooms/materials", "week1.pdf", b"pdf-content")
    ]


@pytest.mark.asyncio
async def test_upload_file_failure_raises():
    class FailingStorage(FakeFileStorage):
        async def upload(self, **kwargs) -> StoredFile:
            del kwargs
            raise RuntimeError("upload failed")

    repo = InMemoryFileRepository()
    service = FileService(repository=repo, storage=FailingStorage())

    with pytest.raises(FileUploadFailedException):
        await service.upload_file(
            file_upload=FileUploadData(
                file_name="week1.pdf",
                mime_type="application/pdf",
                content=BytesIO(b"pdf-content"),
            ),
            directory="classrooms/materials",
        )


@pytest.mark.asyncio
async def test_get_file_not_found():
    repo = InMemoryFileRepository()
    service = FileService(repository=repo, storage=FakeFileStorage())

    with pytest.raises(FileNotFoundException):
        await service.get_file(UUID("00000000-0000-0000-0000-000000000000"))


@pytest.mark.asyncio
async def test_list_files_returns_only_non_deleted_files():
    repo = InMemoryFileRepository()
    service = FileService(repository=repo, storage=FakeFileStorage())
    active_file = await service.create_file(make_create_command())
    deleted_file = await service.create_file(
        CreateFileCommand(
            file_name="old.pdf",
            file_path="uploads/old.pdf",
            file_extension="pdf",
            file_size=2048,
            mime_type="application/pdf",
        )
    )
    await service.delete_file(deleted_file.id)

    files = await service.list_files()

    assert [file.id for file in files] == [active_file.id]


@pytest.mark.asyncio
async def test_update_file_success():
    repo = InMemoryFileRepository()
    service = FileService(repository=repo, storage=FakeFileStorage())
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
    service = FileService(repository=repo, storage=FakeFileStorage())
    created_file = await service.create_file(make_create_command())

    updated_file = await service.update_file(
        created_file.id,
        UpdateFileCommand(file_name="renamed.png"),
    )

    assert updated_file.file_name == "renamed.png"
    assert updated_file.file_path == "uploads/avatar.png"
    assert updated_file.status == FileStatus.PENDING


@pytest.mark.asyncio
async def test_update_file_not_found():
    repo = InMemoryFileRepository()
    service = FileService(repository=repo, storage=FakeFileStorage())

    with pytest.raises(FileNotFoundException):
        await service.update_file(
            UUID("00000000-0000-0000-0000-000000000000"),
            UpdateFileCommand(file_name="missing.pdf"),
        )


@pytest.mark.asyncio
async def test_delete_file_excludes_from_list_and_removes_storage():
    repo = InMemoryFileRepository()
    storage = FakeFileStorage()
    service = FileService(repository=repo, storage=storage)
    created_file = await service.create_file(make_create_command())

    deleted_file = await service.delete_file(created_file.id)
    listed_files = await service.list_files()

    assert deleted_file.status == FileStatus.DELETED
    assert listed_files == []
    assert storage.delete_calls == ["uploads/avatar.png"]


@pytest.mark.asyncio
async def test_delete_file_not_found():
    repo = InMemoryFileRepository()
    service = FileService(repository=repo, storage=FakeFileStorage())

    with pytest.raises(FileNotFoundException):
        await service.delete_file(UUID("00000000-0000-0000-0000-000000000000"))


@pytest.mark.asyncio
async def test_get_file_download_returns_stream_and_metadata():
    repo = InMemoryFileRepository()
    storage = FakeFileStorage()
    service = FileService(repository=repo, storage=storage)
    created_file = await service.upload_file(
        file_upload=FileUploadData(
            file_name="week1.pdf",
            mime_type="application/pdf",
            content=BytesIO(b"pdf-content"),
        ),
        directory="classrooms/materials",
        status=FileStatus.ACTIVE,
    )

    download = await service.get_file_download(created_file.id)

    assert download.file.id == created_file.id
    assert download.file_name == "week1.pdf"
    assert download.mime_type == "application/pdf"
    assert download.content.read() == b"pdf-content"
    assert storage.open_calls == ["classrooms/materials/week1.pdf"]


@pytest.mark.asyncio
async def test_get_file_download_failure_raises():
    class FailingOpenStorage(FakeFileStorage):
        async def open(self, *, path: str):
            self.open_calls.append(path)
            raise RuntimeError("open failed")

    repo = InMemoryFileRepository()
    storage = FailingOpenStorage()
    service = FileService(repository=repo, storage=storage)
    created_file = await service.upload_file(
        file_upload=FileUploadData(
            file_name="week1.pdf",
            mime_type="application/pdf",
            content=BytesIO(b"pdf-content"),
        ),
        directory="classrooms/materials",
        status=FileStatus.ACTIVE,
    )

    with pytest.raises(FileDownloadFailedException):
        await service.get_file_download(created_file.id)


@pytest.mark.asyncio
async def test_delete_file_storage_failure_raises():
    class FailingDeleteStorage(FakeFileStorage):
        async def delete(self, *, path: str) -> None:
            self.delete_calls.append(path)
            raise RuntimeError("delete failed")

    repo = InMemoryFileRepository()
    storage = FailingDeleteStorage()
    service = FileService(repository=repo, storage=storage)
    created_file = await service.create_file(make_create_command())

    with pytest.raises(FileDeleteFailedException):
        await service.delete_file(created_file.id)
