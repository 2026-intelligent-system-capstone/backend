from collections.abc import Sequence
from datetime import datetime
from io import BytesIO
from uuid import UUID

import pytest

from app.auth.application.exception import AuthForbiddenException
from app.auth.domain.entity import CurrentUser
from app.classroom.application.exception import (
    ClassroomMaterialNotFoundException,
)
from app.classroom.application.service import ClassroomService
from app.classroom.domain.command import (
    CreateClassroomMaterialCommand,
    UpdateClassroomMaterialCommand,
)
from app.classroom.domain.entity import (
    Classroom,
    ClassroomMaterial,
    ClassroomMaterialIngestStatus,
    ClassroomMaterialScopeCandidate,
)
from app.classroom.domain.exception import (
    ClassroomMaterialIngestDomainException,
)
from app.classroom.domain.repository import (
    ClassroomMaterialRepository,
    ClassroomRepository,
)
from app.classroom.domain.service import (
    ClassroomMaterialIngestPort,
    ClassroomMaterialIngestResult,
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
        *,
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
        return FileDownload(file=file, content=BytesIO(b"downloaded-content"))

    async def update_file(self, file_id: UUID, command):
        del file_id, command
        raise NotImplementedError

    async def delete_file(self, file_id: UUID) -> File:
        self.deleted_file_ids.append(file_id)
        file = self.files[file_id]
        file.delete()
        return file


class FakeMaterialIngestPort(ClassroomMaterialIngestPort):
    def __init__(
        self,
        *,
        result: ClassroomMaterialIngestResult | None = None,
        error: Exception | None = None,
    ):
        self.result = result or ClassroomMaterialIngestResult()
        self.error = error
        self.requests = []

    async def ingest_material(self, *, request):
        self.requests.append(request)
        if self.error is not None:
            raise self.error
        return self.result


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


def build_service(
    *,
    materials: list[ClassroomMaterial] | None = None,
    allow_student_material_access: bool = False,
    file_usecase: FakeFileUseCase | None = None,
    material_ingest_port: FakeMaterialIngestPort | None = None,
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
        material_repository=InMemoryClassroomMaterialRepository(materials),
        file_usecase=file_usecase or FakeFileUseCase(),
        material_ingest_port=material_ingest_port,
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
    file_usecase = FakeFileUseCase()
    service = build_service(file_usecase=file_usecase)

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
    assert (
        result.material.ingest_status
        is ClassroomMaterialIngestStatus.PENDING
    )
    assert result.material.scope_candidates == []
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
async def test_create_classroom_material_runs_ingest_and_stores_scopes(
):
    file_usecase = FakeFileUseCase()
    ingest_port = FakeMaterialIngestPort(
        result=ClassroomMaterialIngestResult(
            scope_candidates=[
                ClassroomMaterialScopeCandidate(
                    label="기초 개념",
                    scope_text="머신러닝 개요와 지도학습",
                    keywords=["머신러닝", "지도학습"],
                    week_range="1주차",
                    confidence=0.92,
                )
            ]
        )
    )
    service = build_service(
        file_usecase=file_usecase,
        material_ingest_port=ingest_port,
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

    assert len(ingest_port.requests) == 1
    request = ingest_port.requests[0]
    assert request.classroom_id == CLASSROOM_ID
    assert request.title == "1주차 자료"
    assert request.file_name == "week1.pdf"
    assert request.content == b"downloaded-content"
    assert file_usecase.downloaded_file_ids == [FILE_ID]
    assert (
        result.material.ingest_status
        is ClassroomMaterialIngestStatus.COMPLETED
    )
    assert result.material.get_scope_candidates()[0].label == "기초 개념"
    assert result.material.ingest_error is None


@pytest.mark.asyncio
async def test_create_classroom_material_marks_ingest_failed_when_port_raises():
    file_usecase = FakeFileUseCase()
    ingest_port = FakeMaterialIngestPort(
        error=ClassroomMaterialIngestDomainException(
            message="qdrant unavailable"
        )
    )
    service = build_service(
        file_usecase=file_usecase,
        material_ingest_port=ingest_port,
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

    assert len(ingest_port.requests) == 1
    assert (
        result.material.ingest_status
        is ClassroomMaterialIngestStatus.FAILED
    )
    assert result.material.ingest_error == "qdrant unavailable"
    assert result.material.scope_candidates == []


@pytest.mark.asyncio
async def test_create_classroom_material_marks_ingest_failed_on_empty_result(
):
    file_usecase = FakeFileUseCase()
    ingest_port = FakeMaterialIngestPort(
        result=ClassroomMaterialIngestResult(scope_candidates=[])
    )
    service = build_service(
        file_usecase=file_usecase,
        material_ingest_port=ingest_port,
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

    assert len(ingest_port.requests) == 1
    assert (
        result.material.ingest_status
        is ClassroomMaterialIngestStatus.FAILED
    )
    assert (
        result.material.ingest_error
        == "자료에서 시험 범위 후보를 추출하지 못했습니다."
    )
    assert result.material.scope_candidates == []


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
    service = build_service(
        materials=[material],
        allow_student_material_access=True,
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
    service = build_service(materials=[make_material()])

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
    service = build_service(
        materials=[material],
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
    assert (
        result.material.ingest_status
        is ClassroomMaterialIngestStatus.PENDING
    )
    assert result.material.scope_candidates == []
    assert file_usecase.deleted_file_ids == [FILE_ID]
    assert result.file.file_name == "week1-v2.pdf"


@pytest.mark.asyncio
async def test_update_classroom_material_with_file_runs_ingest_again():
    material = make_material()
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
    ingest_port = FakeMaterialIngestPort(
        result=ClassroomMaterialIngestResult(
            scope_candidates=[
                ClassroomMaterialScopeCandidate(
                    label="심화 범위",
                    scope_text="회귀 모델 비교",
                    keywords=["회귀", "모델 비교"],
                    week_range="2주차",
                    confidence=0.88,
                )
            ]
        )
    )
    service = build_service(
        materials=[material],
        file_usecase=file_usecase,
        material_ingest_port=ingest_port,
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

    assert len(ingest_port.requests) == 1
    request = ingest_port.requests[0]
    assert request.file_name == "week1-v2.pdf"
    assert request.content == b"downloaded-content"
    assert file_usecase.downloaded_file_ids == [REPLACEMENT_FILE_ID]
    assert (
        result.material.ingest_status
        is ClassroomMaterialIngestStatus.COMPLETED
    )
    assert (
        result.material.get_scope_candidates()[0].scope_text
        == "회귀 모델 비교"
    )


@pytest.mark.asyncio
async def test_update_classroom_material_with_file_marks_ingest_failed(
):
    material = make_material()
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
    ingest_port = FakeMaterialIngestPort(
        result=ClassroomMaterialIngestResult(scope_candidates=[])
    )
    service = build_service(
        materials=[material],
        file_usecase=file_usecase,
        material_ingest_port=ingest_port,
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

    assert len(ingest_port.requests) == 1
    assert (
        result.material.ingest_status
        is ClassroomMaterialIngestStatus.FAILED
    )
    assert (
        result.material.ingest_error
        == "자료에서 시험 범위 후보를 추출하지 못했습니다."
    )
    assert result.material.scope_candidates == []


@pytest.mark.asyncio
async def test_update_material_metadata_reuses_existing_file_and_reingests(
):
    material = make_material()
    material.mark_ingest_completed(
        [
            ClassroomMaterialScopeCandidate(
                label="기존 범위",
                scope_text="기존 추출 결과",
                keywords=["기존"],
                week_range="1주차",
                confidence=0.5,
            )
        ]
    )
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
    ingest_port = FakeMaterialIngestPort(
        result=ClassroomMaterialIngestResult(
            scope_candidates=[
                ClassroomMaterialScopeCandidate(
                    label="새 범위",
                    scope_text="업데이트된 메타데이터 기준 추출 결과",
                    keywords=["업데이트"],
                    week_range="2주차",
                    confidence=0.91,
                )
            ]
        )
    )
    service = build_service(
        materials=[material],
        file_usecase=file_usecase,
        material_ingest_port=ingest_port,
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

    assert len(ingest_port.requests) == 1
    request = ingest_port.requests[0]
    assert request.title == "메타데이터만 수정"
    assert request.week == 2
    assert request.description is None
    assert request.file_name == "week1.pdf"
    assert request.content == b"downloaded-content"
    assert result.material.title == "메타데이터만 수정"
    assert result.material.week == 2
    assert result.material.file_id == FILE_ID
    assert result.file.id == FILE_ID
    assert (
        result.material.ingest_status
        is ClassroomMaterialIngestStatus.COMPLETED
    )
    assert result.material.get_scope_candidates()[0].label == "새 범위"
    assert file_usecase.downloaded_file_ids == [FILE_ID]
    assert file_usecase.uploaded_payloads == []
    assert file_usecase.deleted_file_ids == []


@pytest.mark.asyncio
async def test_update_material_description_reuses_existing_file_and_reingests(
):
    material = make_material()
    material.mark_ingest_completed(
        [
            ClassroomMaterialScopeCandidate(
                label="기존 범위",
                scope_text="기존 추출 결과",
                keywords=["기존"],
                week_range="1주차",
                confidence=0.5,
            )
        ]
    )
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
    ingest_port = FakeMaterialIngestPort(
        result=ClassroomMaterialIngestResult(
            scope_candidates=[
                ClassroomMaterialScopeCandidate(
                    label="설명 변경 범위",
                    scope_text="설명 변경 기준 추출 결과",
                    keywords=["설명"],
                    week_range="1주차",
                    confidence=0.77,
                )
            ]
        )
    )
    service = build_service(
        materials=[material],
        file_usecase=file_usecase,
        material_ingest_port=ingest_port,
    )

    result = await service.update_classroom_material(
        classroom_id=CLASSROOM_ID,
        material_id=MATERIAL_ID,
        current_user=make_current_user(
            role=UserRole.PROFESSOR,
            user_id=PROFESSOR_ID,
        ),
        command=UpdateClassroomMaterialCommand(description="설명 수정"),
    )

    assert len(ingest_port.requests) == 1
    request = ingest_port.requests[0]
    assert request.title == "1주차 자료"
    assert request.week == 1
    assert request.description == "설명 수정"
    assert request.file_name == "week1.pdf"
    assert result.material.description == "설명 수정"
    assert (
        result.material.ingest_status
        is ClassroomMaterialIngestStatus.COMPLETED
    )
    assert result.material.get_scope_candidates()[0].label == "설명 변경 범위"
    assert file_usecase.downloaded_file_ids == [FILE_ID]


@pytest.mark.asyncio
async def test_update_material_metadata_marks_ingest_failed_on_empty_result(
):
    material = make_material()
    material.mark_ingest_completed(
        [
            ClassroomMaterialScopeCandidate(
                label="기존 범위",
                scope_text="기존 추출 결과",
                keywords=["기존"],
                week_range="1주차",
                confidence=0.5,
            )
        ]
    )
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
    ingest_port = FakeMaterialIngestPort(
        result=ClassroomMaterialIngestResult(scope_candidates=[])
    )
    service = build_service(
        materials=[material],
        file_usecase=file_usecase,
        material_ingest_port=ingest_port,
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
            description="설명 수정",
        ),
    )

    assert len(ingest_port.requests) == 1
    assert (
        result.material.ingest_status
        is ClassroomMaterialIngestStatus.FAILED
    )
    assert (
        result.material.ingest_error
        == "자료에서 시험 범위 후보를 추출하지 못했습니다."
    )
    assert result.material.scope_candidates == []
    assert file_usecase.downloaded_file_ids == [FILE_ID]


@pytest.mark.asyncio
async def test_update_classroom_material_metadata_noop_does_not_reingest():
    material = make_material()
    material.mark_ingest_completed(
        [
            ClassroomMaterialScopeCandidate(
                label="기존 범위",
                scope_text="기존 추출 결과",
                keywords=["기존"],
                week_range="1주차",
                confidence=0.5,
            )
        ]
    )
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
    ingest_port = FakeMaterialIngestPort(
        result=ClassroomMaterialIngestResult(scope_candidates=[])
    )
    service = build_service(
        materials=[material],
        file_usecase=file_usecase,
        material_ingest_port=ingest_port,
    )

    result = await service.update_classroom_material(
        classroom_id=CLASSROOM_ID,
        material_id=MATERIAL_ID,
        current_user=make_current_user(
            role=UserRole.PROFESSOR,
            user_id=PROFESSOR_ID,
        ),
        command=UpdateClassroomMaterialCommand(
            title="1주차 자료",
            week=1,
            description="소개 자료",
        ),
    )

    assert len(ingest_port.requests) == 0
    assert (
        result.material.ingest_status
        is ClassroomMaterialIngestStatus.COMPLETED
    )
    assert result.material.get_scope_candidates()[0].label == "기존 범위"
    assert file_usecase.downloaded_file_ids == []
    assert file_usecase.uploaded_payloads == []
    assert file_usecase.deleted_file_ids == []


@pytest.mark.asyncio
async def test_reingest_classroom_material_runs_ingest_again_for_existing_file(
):
    material = make_material()
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
    ingest_port = FakeMaterialIngestPort(
        result=ClassroomMaterialIngestResult(
            scope_candidates=[
                ClassroomMaterialScopeCandidate(
                    label="재적재 범위",
                    scope_text="의사결정나무와 앙상블",
                    keywords=["의사결정나무", "앙상블"],
                    week_range="3주차",
                    confidence=0.81,
                )
            ]
        )
    )
    service = build_service(
        materials=[material],
        file_usecase=file_usecase,
        material_ingest_port=ingest_port,
    )

    result = await service.reingest_classroom_material(
        classroom_id=CLASSROOM_ID,
        material_id=MATERIAL_ID,
        current_user=make_current_user(
            role=UserRole.PROFESSOR,
            user_id=PROFESSOR_ID,
        ),
    )

    assert len(ingest_port.requests) == 1
    request = ingest_port.requests[0]
    assert request.material_id == MATERIAL_ID
    assert request.file_name == "week1.pdf"
    assert request.content == b"downloaded-content"
    assert file_usecase.downloaded_file_ids == [FILE_ID]
    assert (
        result.material.ingest_status
        is ClassroomMaterialIngestStatus.COMPLETED
    )
    assert result.material.get_scope_candidates()[0].label == "재적재 범위"


@pytest.mark.asyncio
async def test_reingest_classroom_material_marks_failed_when_result_empty():
    material = make_material()
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
    ingest_port = FakeMaterialIngestPort(
        result=ClassroomMaterialIngestResult(scope_candidates=[])
    )
    service = build_service(
        materials=[material],
        file_usecase=file_usecase,
        material_ingest_port=ingest_port,
    )

    result = await service.reingest_classroom_material(
        classroom_id=CLASSROOM_ID,
        material_id=MATERIAL_ID,
        current_user=make_current_user(
            role=UserRole.PROFESSOR,
            user_id=PROFESSOR_ID,
        ),
    )

    assert (
        result.material.ingest_status
        is ClassroomMaterialIngestStatus.FAILED
    )
    assert (
        result.material.ingest_error
        == "자료에서 시험 범위 후보를 추출하지 못했습니다."
    )
    assert result.material.scope_candidates == []


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
    service = build_service(
        materials=[make_other_classroom_material()],
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
    service = build_service(materials=[make_other_classroom_material()])

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
    service = build_service(
        materials=[material],
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
    assert file_usecase.deleted_file_ids == [FILE_ID]


@pytest.mark.asyncio
async def test_get_classroom_material_not_found_raises():
    service = build_service()

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
    service = build_service(
        materials=[material],
        allow_student_material_access=True,
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
