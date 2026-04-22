from collections.abc import Sequence
from io import BytesIO
from uuid import UUID

import pytest

from app.auth.application.exception import AuthForbiddenException
from app.auth.domain.entity import CurrentUser
from app.classroom.application.service import ClassroomService
from app.classroom.domain.command import CreateClassroomMaterialCommand
from app.classroom.domain.entity import Classroom, ClassroomMaterial
from app.classroom.domain.repository import (
    ClassroomMaterialRepository,
    ClassroomRepository,
)
from app.file.domain.entity.file import File, FileStatus
from app.file.domain.entity.file_download import FileDownload
from app.file.domain.service import FileUploadData
from app.file.domain.usecase.file import FileUseCase
from app.user.domain.entity import User, UserRole
from app.user.domain.repository import UserRepository

ORG_ID = UUID("11111111-1111-1111-1111-111111111111")
CLASSROOM_ID = UUID("22222222-2222-2222-2222-222222222222")
PROFESSOR_ID = UUID("33333333-3333-3333-3333-333333333333")
STUDENT_ID = UUID("44444444-4444-4444-4444-444444444444")
MATERIAL_ID = UUID("55555555-5555-5555-5555-555555555555")
FILE_ID = UUID("66666666-6666-6666-6666-666666666666")


class InMemoryClassroomRepository(ClassroomRepository):
    def __init__(self, classrooms: list[Classroom] | None = None):
        self.classrooms = {
            classroom.id: classroom for classroom in classrooms or []
        }

    async def save(self, entity: Classroom) -> None:
        self.classrooms[entity.id] = entity

    async def get_by_id(self, entity_id: UUID) -> Classroom | None:
        return self.classrooms.get(entity_id)

    async def list(self) -> list[Classroom]:
        return list(self.classrooms.values())

    async def get_by_organization_and_name_and_term(
        self,
        organization_id: UUID,
        name: str,
        grade: int,
        semester: str,
        section: str,
    ) -> Classroom | None:
        for classroom in self.classrooms.values():
            if (
                classroom.organization_id == organization_id
                and classroom.name == name
                and classroom.grade == grade
                and classroom.semester == semester
                and classroom.section == section
            ):
                return classroom
        return None

    async def list_by_organization(
        self, organization_id: UUID
    ) -> Sequence[Classroom]:
        return [
            classroom
            for classroom in self.classrooms.values()
            if classroom.organization_id == organization_id
        ]

    async def delete(self, entity: Classroom) -> None:
        self.classrooms.pop(entity.id, None)


class InMemoryUserRepository(UserRepository):
    def __init__(self, users: list[User]):
        self.users = {user.id: user for user in users}

    async def save(self, entity: User) -> None:
        self.users[entity.id] = entity

    async def get_by_id(self, entity_id: UUID) -> User | None:
        return self.users.get(entity_id)

    async def list(self) -> list[User]:
        return list(self.users.values())

    async def list_by_organization(
        self, organization_id: UUID
    ) -> Sequence[User]:
        return [
            user
            for user in self.users.values()
            if user.organization_id == organization_id
        ]

    async def get_by_organization_and_login_id(
        self,
        organization_id: UUID,
        login_id: str,
    ) -> User | None:
        for user in self.users.values():
            if (
                user.organization_id == organization_id
                and user.login_id == login_id
            ):
                return user
        return None


class InMemoryClassroomMaterialRepository(ClassroomMaterialRepository):
    def __init__(self, materials: list[ClassroomMaterial] | None = None):
        self.materials = {material.id: material for material in materials or []}

    async def save(self, entity: ClassroomMaterial) -> None:
        self.materials[entity.id] = entity

    async def get_by_id(self, entity_id: UUID) -> ClassroomMaterial | None:
        return self.materials.get(entity_id)

    async def list(self) -> list[ClassroomMaterial]:
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


class FakeFileUseCase(FileUseCase):
    def __init__(self):
        self.files: dict[UUID, File] = {}
        self.uploaded_payloads: list[tuple[str, str, bytes, FileStatus]] = []
        self.downloaded_file_ids: list[UUID] = []

    async def create_file(self, command):
        raise NotImplementedError

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
        file = File(
            file_name=file_upload.file_name,
            file_path=f"{directory}/{file_upload.file_name}",
            file_extension=file_upload.file_name.rsplit(".", 1)[-1],
            file_size=len(content),
            mime_type=file_upload.mime_type,
            status=status,
        )
        file.id = FILE_ID
        self.files[file.id] = file
        return file

    async def list_files(self) -> list[File]:
        return list(self.files.values())

    async def get_file(self, file_id: UUID) -> File:
        return self.files[file_id]

    async def get_file_download(self, file_id: UUID) -> FileDownload:
        self.downloaded_file_ids.append(file_id)
        file = self.files[file_id]
        return FileDownload(
            file=file,
            content=BytesIO(b"downloaded-content"),
        )

    async def update_file(self, file_id: UUID, command):
        raise NotImplementedError

    async def delete_file(self, file_id: UUID) -> File:
        raise NotImplementedError


def make_user(user_id: UUID, role: UserRole) -> User:
    user = User(
        organization_id=ORG_ID,
        login_id=str(user_id.int)[:7],
        role=role,
        email=f"{user_id}@example.com",
        name="사용자",
    )
    user.id = user_id
    return user


def make_classroom(*, allow_student_material_access: bool = False) -> Classroom:
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


def build_service(
    *, allow_student_material_access: bool = False
) -> ClassroomService:
    return ClassroomService(
        repository=InMemoryClassroomRepository([
            make_classroom(
                allow_student_material_access=allow_student_material_access
            )
        ]),
        user_repository=InMemoryUserRepository([
            make_user(PROFESSOR_ID, UserRole.PROFESSOR),
            make_user(STUDENT_ID, UserRole.STUDENT),
        ]),
        material_repository=InMemoryClassroomMaterialRepository(),
        file_usecase=FakeFileUseCase(),
    )


@pytest.mark.asyncio
async def test_create_classroom_material_success_via_classroom_service():
    service = build_service()

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
            source_kind="file",
        ),
        file_upload=FileUploadData(
            file_name="week1.pdf",
            mime_type="application/pdf",
            content=BytesIO(b"pdf-content"),
        ),
    )

    assert result.material.classroom_id == CLASSROOM_ID
    assert result.material.title == "1주차 자료"
    assert result.file.file_name == "week1.pdf"


@pytest.mark.asyncio
async def test_list_materials_without_access_raises_via_classroom_service():
    service = build_service()

    with pytest.raises(AuthForbiddenException):
        await service.list_classroom_materials(
            classroom_id=CLASSROOM_ID,
            current_user=make_current_user(
                role=UserRole.STUDENT,
                user_id=STUDENT_ID,
            ),
        )
