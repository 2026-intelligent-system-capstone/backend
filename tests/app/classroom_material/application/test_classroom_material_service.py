from collections.abc import Sequence
from datetime import datetime
from io import BytesIO
from uuid import UUID

import pytest

from app.auth.application.exception import AuthForbiddenException
from app.auth.domain.entity import CurrentUser
from app.classroom.domain.entity import Classroom
from app.classroom.domain.usecase import ClassroomUseCase
from app.classroom_material.application.exception import (
    ClassroomMaterialNotFoundException,
)
from app.classroom_material.application.service import ClassroomMaterialService
from app.classroom_material.domain.command import (
    CreateClassroomMaterialCommand,
    UpdateClassroomMaterialCommand,
)
from app.classroom_material.domain.entity import ClassroomMaterial
from app.classroom_material.domain.repository import ClassroomMaterialRepository
from app.file.domain.entity.file import File, FileStatus
from app.file.domain.service import FileUploadData
from app.file.domain.usecase.file import FileUseCase
from app.user.domain.entity import UserRole

ORG_ID = UUID("11111111-1111-1111-1111-111111111111")
CLASSROOM_ID = UUID("22222222-2222-2222-2222-222222222222")
PROFESSOR_ID = UUID("33333333-3333-3333-3333-333333333333")
STUDENT_ID = UUID("44444444-4444-4444-4444-444444444444")
MATERIAL_ID = UUID("55555555-5555-5555-5555-555555555555")
FILE_ID = UUID("66666666-6666-6666-6666-666666666666")
REPLACEMENT_FILE_ID = UUID("77777777-7777-7777-7777-777777777777")


class InMemoryClassroomMaterialRepository(ClassroomMaterialRepository):
    def __init__(self, materials: list[ClassroomMaterial] | None = None):
        self.materials = {material.id: material for material in materials or []}

    async def save(self, entity: ClassroomMaterial) -> None:
        self.materials[entity.id] = entity

    async def get_by_id(self, entity_id: UUID) -> ClassroomMaterial | None:
        return self.materials.get(entity_id)

    async def list(self) -> Sequence[ClassroomMaterial]:
        return list(self.materials.values())

    async def list_by_classroom(
        self,
        classroom_id: UUID,
    ) -> Sequence[ClassroomMaterial]:
        return [
            material
            for material in self.materials.values()
            if material.classroom_id == classroom_id
        ]

    async def delete(self, entity: ClassroomMaterial) -> None:
        self.materials.pop(entity.id, None)


class FakeClassroomUseCase(ClassroomUseCase):
    def __init__(self, classroom: Classroom):
        self.classroom = classroom

    async def create_classroom(self, **kwargs):
        raise NotImplementedError

    async def get_classroom(
        self, *, classroom_id: UUID, current_user: CurrentUser
    ):
        del classroom_id, current_user
        return self.classroom

    async def get_manageable_classroom(
        self,
        *,
        classroom_id: UUID,
        current_user: CurrentUser,
    ) -> Classroom:
        del classroom_id, current_user
        return self.classroom

    async def list_classrooms(self, *, current_user: CurrentUser):
        del current_user
        return [self.classroom]

    async def update_classroom(self, **kwargs):
        raise NotImplementedError

    async def delete_classroom(self, **kwargs):
        raise NotImplementedError

    async def invite_classroom_students(self, **kwargs):
        raise NotImplementedError

    async def remove_classroom_student(self, **kwargs):
        raise NotImplementedError


class FakeFileUseCase(FileUseCase):
    def __init__(self):
        self.files: dict[UUID, File] = {}
        self.deleted_file_ids: list[UUID] = []
        self.uploaded_payloads: list[tuple[str, str, bytes, FileStatus]] = []
        self.downloaded_file_ids: list[UUID] = []

    async def create_file(self, command):
        file = File(
            file_name=command.file_name,
            file_path=command.file_path,
            file_extension=command.file_extension,
            file_size=command.file_size,
            mime_type=command.mime_type,
        )
        self.files[file.id] = file
        return file

    async def upload_file(
        self,
        *,
        file_upload: FileUploadData,
        directory: str,
        status: FileStatus = FileStatus.PENDING,
    ) -> File:
        file_upload.content.seek(0)
        content = file_upload.content.read()
        self.uploaded_payloads.append((
            directory,
            file_upload.file_name,
            content,
            status,
        ))
        next_id = FILE_ID if not self.files else REPLACEMENT_FILE_ID
        file = File(
            file_name=file_upload.file_name,
            file_path=f"{directory}/{file_upload.file_name}",
            file_extension=file_upload.file_name.rsplit(".", 1)[-1],
            file_size=len(content),
            mime_type=file_upload.mime_type,
            status=status,
        )
        file.id = next_id
        self.files[file.id] = file
        return file

    async def list_files(self) -> list[File]:
        return list(self.files.values())

    async def get_file(self, file_id: UUID) -> File:
        return self.files[file_id]

    async def get_file_download(self, file_id: UUID):
        self.downloaded_file_ids.append(file_id)
        file = self.files[file_id]
        return type(
            "FileDownload",
            (),
            {
                "file": file,
                "file_name": file.file_name,
                "mime_type": file.mime_type,
                "content": BytesIO(b"downloaded-content"),
            },
        )()

    async def update_file(self, file_id: UUID, command):
        del file_id, command
        raise NotImplementedError

    async def delete_file(self, file_id: UUID) -> File:
        self.deleted_file_ids.append(file_id)
        file = self.files[file_id]
        file.delete()
        return file


def make_classroom(
    *,
    allow_student_material_access: bool = False,
) -> Classroom:
    classroom = Classroom(
        organization_id=ORG_ID,
        name="AI 기초",
        professor_ids=[PROFESSOR_ID],
        grade=3,
        semester="1학기",
        section="01",
        description="AI 입문 강의실",
        student_ids=[STUDENT_ID],
        allow_student_material_access=allow_student_material_access,
    )
    classroom.id = CLASSROOM_ID
    return classroom


def make_current_user(*, role: UserRole, user_id: UUID) -> CurrentUser:
    return CurrentUser(
        id=user_id,
        organization_id=ORG_ID,
        login_id="user01",
        role=role,
    )


def make_material() -> ClassroomMaterial:
    material = ClassroomMaterial(
        classroom_id=CLASSROOM_ID,
        file_id=FILE_ID,
        title="1주차 자료",
        week=1,
        description="소개 자료",
        uploaded_by=PROFESSOR_ID,
        created_at=datetime(2026, 1, 1, 9, 0, 0),
    )
    material.id = MATERIAL_ID
    return material


def make_other_classroom_material() -> ClassroomMaterial:
    material = make_material()
    material.classroom_id = UUID("88888888-8888-8888-8888-888888888888")
    return material


@pytest.mark.asyncio
async def test_create_classroom_material_success():
    repository = InMemoryClassroomMaterialRepository()
    file_usecase = FakeFileUseCase()
    service = ClassroomMaterialService(
        repository=repository,
        classroom_usecase=FakeClassroomUseCase(make_classroom()),
        file_usecase=file_usecase,
    )

    result = await service.create_classroom_material(
        classroom_id=CLASSROOM_ID,
        current_user=make_current_user(
            role=UserRole.PROFESSOR,
            user_id=PROFESSOR_ID,
        ),
        command=CreateClassroomMaterialCommand(
            title="1주차 자료",
            week=1,
            description="소개 자료",
        ),
        file_upload=FileUploadData(
            file_name="week1.pdf",
            mime_type="application/pdf",
            content=BytesIO(b"pdf-content"),
        ),
    )

    assert result.material.title == "1주차 자료"
    assert result.material.file_id == FILE_ID
    assert result.file.file_name == "week1.pdf"
    assert file_usecase.uploaded_payloads == [
        (
            f"classrooms/{CLASSROOM_ID}/materials",
            "week1.pdf",
            b"pdf-content",
            FileStatus.ACTIVE,
        )
    ]


@pytest.mark.asyncio
async def test_list_classroom_materials_for_student_with_access():
    material = make_material()
    file_usecase = FakeFileUseCase()
    file_usecase.files[FILE_ID] = File(
        file_name="week1.pdf",
        file_path="classrooms/week1.pdf",
        file_extension="pdf",
        file_size=10,
        mime_type="application/pdf",
        status=FileStatus.ACTIVE,
    )
    file_usecase.files[FILE_ID].id = FILE_ID
    service = ClassroomMaterialService(
        repository=InMemoryClassroomMaterialRepository([material]),
        classroom_usecase=FakeClassroomUseCase(
            make_classroom(allow_student_material_access=True)
        ),
        file_usecase=file_usecase,
    )

    results = await service.list_classroom_materials(
        classroom_id=CLASSROOM_ID,
        current_user=make_current_user(
            role=UserRole.STUDENT,
            user_id=STUDENT_ID,
        ),
    )

    assert len(results) == 1
    assert results[0].material.id == MATERIAL_ID


@pytest.mark.asyncio
async def test_list_classroom_materials_for_student_without_access_raises():
    service = ClassroomMaterialService(
        repository=InMemoryClassroomMaterialRepository([make_material()]),
        classroom_usecase=FakeClassroomUseCase(make_classroom()),
        file_usecase=FakeFileUseCase(),
    )

    with pytest.raises(AuthForbiddenException):
        await service.list_classroom_materials(
            classroom_id=CLASSROOM_ID,
            current_user=make_current_user(
                role=UserRole.STUDENT,
                user_id=STUDENT_ID,
            ),
        )


@pytest.mark.asyncio
async def test_update_classroom_material_replaces_file_and_deletes_old():
    material = make_material()
    repository = InMemoryClassroomMaterialRepository([material])
    file_usecase = FakeFileUseCase()
    old_file = File(
        file_name="week1.pdf",
        file_path="classrooms/week1.pdf",
        file_extension="pdf",
        file_size=10,
        mime_type="application/pdf",
        status=FileStatus.ACTIVE,
    )
    old_file.id = FILE_ID
    file_usecase.files[FILE_ID] = old_file
    service = ClassroomMaterialService(
        repository=repository,
        classroom_usecase=FakeClassroomUseCase(make_classroom()),
        file_usecase=file_usecase,
    )

    result = await service.update_classroom_material(
        classroom_id=CLASSROOM_ID,
        material_id=MATERIAL_ID,
        current_user=make_current_user(
            role=UserRole.PROFESSOR,
            user_id=PROFESSOR_ID,
        ),
        command=UpdateClassroomMaterialCommand(
            title="수정 자료",
            week=1,
            description="소개 자료",
        ),
        file_upload=FileUploadData(
            file_name="week1-v2.pdf",
            mime_type="application/pdf",
            content=BytesIO(b"new-pdf-content"),
        ),
    )

    assert result.material.title == "수정 자료"
    assert result.material.file_id == REPLACEMENT_FILE_ID
    assert file_usecase.deleted_file_ids == [FILE_ID]
    assert result.file.file_name == "week1-v2.pdf"


@pytest.mark.asyncio
async def test_update_classroom_material_metadata_only_keeps_existing_file():
    material = make_material()
    repository = InMemoryClassroomMaterialRepository([material])
    file_usecase = FakeFileUseCase()
    current_file = File(
        file_name="week1.pdf",
        file_path="classrooms/week1.pdf",
        file_extension="pdf",
        file_size=10,
        mime_type="application/pdf",
        status=FileStatus.ACTIVE,
    )
    current_file.id = FILE_ID
    file_usecase.files[FILE_ID] = current_file
    service = ClassroomMaterialService(
        repository=repository,
        classroom_usecase=FakeClassroomUseCase(make_classroom()),
        file_usecase=file_usecase,
    )

    result = await service.update_classroom_material(
        classroom_id=CLASSROOM_ID,
        material_id=MATERIAL_ID,
        current_user=make_current_user(
            role=UserRole.PROFESSOR,
            user_id=PROFESSOR_ID,
        ),
        command=UpdateClassroomMaterialCommand(
            title="메타데이터만 수정",
            week=2,
            description=None,
        ),
    )

    assert result.material.title == "메타데이터만 수정"
    assert result.material.week == 2
    assert result.material.file_id == FILE_ID
    assert result.file.id == FILE_ID
    assert file_usecase.uploaded_payloads == []
    assert file_usecase.deleted_file_ids == []


@pytest.mark.asyncio
async def test_get_classroom_material_from_other_classroom_raises_not_found():
    file_usecase = FakeFileUseCase()
    file_usecase.files[FILE_ID] = File(
        file_name="week1.pdf",
        file_path="classrooms/week1.pdf",
        file_extension="pdf",
        file_size=10,
        mime_type="application/pdf",
        status=FileStatus.ACTIVE,
    )
    file_usecase.files[FILE_ID].id = FILE_ID
    service = ClassroomMaterialService(
        repository=InMemoryClassroomMaterialRepository([
            make_other_classroom_material()
        ]),
        classroom_usecase=FakeClassroomUseCase(make_classroom()),
        file_usecase=file_usecase,
    )

    with pytest.raises(ClassroomMaterialNotFoundException):
        await service.get_classroom_material(
            classroom_id=CLASSROOM_ID,
            material_id=MATERIAL_ID,
            current_user=make_current_user(
                role=UserRole.PROFESSOR,
                user_id=PROFESSOR_ID,
            ),
        )


@pytest.mark.asyncio
async def test_delete_other_classroom_material_raises_not_found():
    service = ClassroomMaterialService(
        repository=InMemoryClassroomMaterialRepository([
            make_other_classroom_material()
        ]),
        classroom_usecase=FakeClassroomUseCase(make_classroom()),
        file_usecase=FakeFileUseCase(),
    )

    with pytest.raises(ClassroomMaterialNotFoundException):
        await service.delete_classroom_material(
            classroom_id=CLASSROOM_ID,
            material_id=MATERIAL_ID,
            current_user=make_current_user(
                role=UserRole.PROFESSOR,
                user_id=PROFESSOR_ID,
            ),
        )


@pytest.mark.asyncio
async def test_delete_classroom_material_deletes_material_and_file():
    material = make_material()
    repository = InMemoryClassroomMaterialRepository([material])
    file_usecase = FakeFileUseCase()
    file = File(
        file_name="week1.pdf",
        file_path="classrooms/week1.pdf",
        file_extension="pdf",
        file_size=10,
        mime_type="application/pdf",
        status=FileStatus.ACTIVE,
    )
    file.id = FILE_ID
    file_usecase.files[FILE_ID] = file
    service = ClassroomMaterialService(
        repository=repository,
        classroom_usecase=FakeClassroomUseCase(make_classroom()),
        file_usecase=file_usecase,
    )

    result = await service.delete_classroom_material(
        classroom_id=CLASSROOM_ID,
        material_id=MATERIAL_ID,
        current_user=make_current_user(
            role=UserRole.PROFESSOR,
            user_id=PROFESSOR_ID,
        ),
    )

    assert result.material.id == MATERIAL_ID
    assert repository.materials == {}
    assert file_usecase.deleted_file_ids == [FILE_ID]


@pytest.mark.asyncio
async def test_get_classroom_material_not_found_raises():
    service = ClassroomMaterialService(
        repository=InMemoryClassroomMaterialRepository(),
        classroom_usecase=FakeClassroomUseCase(make_classroom()),
        file_usecase=FakeFileUseCase(),
    )

    with pytest.raises(ClassroomMaterialNotFoundException):
        await service.get_classroom_material(
            classroom_id=CLASSROOM_ID,
            material_id=MATERIAL_ID,
            current_user=make_current_user(
                role=UserRole.PROFESSOR,
                user_id=PROFESSOR_ID,
            ),
        )


@pytest.mark.asyncio
async def test_get_classroom_material_download_returns_stream():
    material = make_material()
    file_usecase = FakeFileUseCase()
    file_usecase.files[FILE_ID] = File(
        file_name="week1.pdf",
        file_path="classrooms/week1.pdf",
        file_extension="pdf",
        file_size=10,
        mime_type="application/pdf",
        status=FileStatus.ACTIVE,
    )
    file_usecase.files[FILE_ID].id = FILE_ID
    service = ClassroomMaterialService(
        repository=InMemoryClassroomMaterialRepository([material]),
        classroom_usecase=FakeClassroomUseCase(
            make_classroom(allow_student_material_access=True)
        ),
        file_usecase=file_usecase,
    )

    download = await service.get_classroom_material_download(
        classroom_id=CLASSROOM_ID,
        material_id=MATERIAL_ID,
        current_user=make_current_user(
            role=UserRole.STUDENT,
            user_id=STUDENT_ID,
        ),
    )

    assert download.file_name == "week1.pdf"
    assert download.mime_type == "application/pdf"
    assert download.content.read() == b"downloaded-content"
    assert file_usecase.downloaded_file_ids == [FILE_ID]
