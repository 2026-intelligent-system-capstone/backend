from collections.abc import Sequence
from uuid import UUID, uuid4

import pytest

from app.auth.application.exception import AuthForbiddenException
from app.auth.domain.entity import CurrentUser
from app.classroom.application.exception import (
    ClassroomAlreadyExistsException,
    ClassroomInvalidProfessorRoleException,
    ClassroomInvalidStudentRoleException,
    ClassroomNotFoundException,
    ClassroomStudentAlreadyInvitedException,
    ClassroomStudentNotEnrolledException,
)
from app.classroom.application.service import ClassroomService
from app.classroom.domain.command import (
    CreateClassroomCommand,
    InviteClassroomStudentsCommand,
    RemoveClassroomStudentCommand,
    UpdateClassroomCommand,
)
from app.classroom.domain.entity import Classroom
from app.classroom.domain.repository import ClassroomRepository
from app.user.domain.entity import User, UserRole
from app.user.domain.repository import UserRepository

ORG_ID = UUID("11111111-1111-1111-1111-111111111111")
PROFESSOR_ID = UUID("22222222-2222-2222-2222-222222222222")
SECOND_PROFESSOR_ID = UUID("33333333-3333-3333-3333-333333333333")
STUDENT_ID = UUID("44444444-4444-4444-4444-444444444444")
SECOND_STUDENT_ID = UUID("55555555-5555-5555-5555-555555555555")


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
        return next(
            (
                classroom
                for classroom in self.classrooms.values()
                if classroom.organization_id == organization_id
                and classroom.name == name
                and classroom.grade == grade
                and classroom.semester == semester
                and classroom.section == section
            ),
            None,
        )

    async def list_by_organization(
        self,
        organization_id: UUID,
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
        self,
        organization_id: UUID,
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
        return next(
            (
                user
                for user in self.users.values()
                if user.organization_id == organization_id
                and user.login_id == login_id
            ),
            None,
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


def make_classroom() -> Classroom:
    classroom = Classroom(
        organization_id=ORG_ID,
        name="AI 기초",
        professor_ids=[PROFESSOR_ID],
        grade=3,
        semester="1학기",
        section="01",
        description="AI 입문 강의실",
        student_ids=[STUDENT_ID],
        allow_student_material_access=False,
    )
    classroom.id = UUID("66666666-6666-6666-6666-666666666666")
    return classroom


def make_service(
    classrooms: list[Classroom] | None = None,
    users: list[User] | None = None,
) -> ClassroomService:
    return ClassroomService(
        repository=InMemoryClassroomRepository(classrooms),
        user_repository=InMemoryUserRepository(
            users
            or [
                make_user(PROFESSOR_ID, UserRole.PROFESSOR),
                make_user(SECOND_PROFESSOR_ID, UserRole.PROFESSOR),
                make_user(STUDENT_ID, UserRole.STUDENT),
                make_user(SECOND_STUDENT_ID, UserRole.STUDENT),
            ]
        ),
    )


def make_current_user(
    *,
    role: UserRole = UserRole.STUDENT,
    user_id: UUID = STUDENT_ID,
    organization_id: UUID = ORG_ID,
) -> CurrentUser:
    return CurrentUser(
        id=user_id,
        organization_id=organization_id,
        login_id="current-user",
        role=role,
    )


@pytest.mark.asyncio
async def test_create_classroom_success():
    service = make_service()

    classroom = await service.create_classroom(
        current_user=make_current_user(
            role=UserRole.PROFESSOR,
            user_id=PROFESSOR_ID,
        ),
        command=CreateClassroomCommand(
            organization_id=ORG_ID,
            name="AI 기초",
            professor_ids=[SECOND_PROFESSOR_ID],
            grade=3,
            semester="1학기",
            section="01",
            description="AI 입문 강의실",
            student_ids=[STUDENT_ID],
            allow_student_material_access=True,
        ),
    )

    assert classroom.name == "AI 기초"
    assert classroom.professor_ids == [SECOND_PROFESSOR_ID, PROFESSOR_ID]
    assert classroom.allow_student_material_access is True


@pytest.mark.asyncio
async def test_create_classroom_duplicate_schedule_raises():
    service = make_service([make_classroom()])

    with pytest.raises(ClassroomAlreadyExistsException):
        await service.create_classroom(
            current_user=make_current_user(
                role=UserRole.PROFESSOR,
                user_id=PROFESSOR_ID,
            ),
            command=CreateClassroomCommand(
                organization_id=ORG_ID,
                name="AI 기초",
                professor_ids=[PROFESSOR_ID],
                grade=3,
                semester="1학기",
                section="01",
            ),
        )


@pytest.mark.asyncio
async def test_create_classroom_invalid_professor_role_raises():
    service = make_service(
        users=[
            make_user(PROFESSOR_ID, UserRole.STUDENT),
            make_user(STUDENT_ID, UserRole.STUDENT),
        ]
    )

    with pytest.raises(ClassroomInvalidProfessorRoleException):
        await service.create_classroom(
            current_user=make_current_user(
                role=UserRole.PROFESSOR,
                user_id=PROFESSOR_ID,
            ),
            command=CreateClassroomCommand(
                organization_id=ORG_ID,
                name="AI 기초",
                professor_ids=[PROFESSOR_ID],
                grade=3,
                semester="1학기",
                section="01",
            ),
        )


@pytest.mark.asyncio
async def test_create_classroom_invalid_student_role_raises():
    service = make_service(
        users=[
            make_user(PROFESSOR_ID, UserRole.PROFESSOR),
            make_user(STUDENT_ID, UserRole.PROFESSOR),
        ]
    )

    with pytest.raises(ClassroomInvalidStudentRoleException):
        await service.create_classroom(
            current_user=make_current_user(
                role=UserRole.PROFESSOR,
                user_id=PROFESSOR_ID,
            ),
            command=CreateClassroomCommand(
                organization_id=ORG_ID,
                name="AI 기초",
                professor_ids=[PROFESSOR_ID],
                grade=3,
                semester="1학기",
                section="01",
                student_ids=[STUDENT_ID],
            ),
        )


@pytest.mark.asyncio
async def test_list_classrooms_returns_only_accessible_classrooms():
    another_classroom = Classroom(
        organization_id=ORG_ID,
        name="데이터 과학",
        professor_ids=[SECOND_PROFESSOR_ID],
        grade=2,
        semester="2학기",
        section="02",
        description=None,
        student_ids=[],
        allow_student_material_access=False,
    )
    another_classroom.id = uuid4()
    service = make_service([make_classroom(), another_classroom])

    classrooms = await service.list_classrooms(
        current_user=make_current_user(),
    )

    assert len(classrooms) == 1
    assert classrooms[0].name == "AI 기초"


@pytest.mark.asyncio
async def test_get_classroom_not_found_raises():
    service = make_service()

    with pytest.raises(ClassroomNotFoundException):
        await service.get_classroom(
            classroom_id=uuid4(),
            current_user=make_current_user(),
        )


@pytest.mark.asyncio
async def test_get_classroom_forbidden_for_other_organization_user():
    service = make_service([make_classroom()])

    with pytest.raises(AuthForbiddenException):
        await service.get_classroom(
            classroom_id=UUID("66666666-6666-6666-6666-666666666666"),
            current_user=make_current_user(organization_id=uuid4()),
        )


@pytest.mark.asyncio
async def test_update_classroom_success():
    service = make_service([make_classroom()])

    classroom = await service.update_classroom(
        classroom_id=UUID("66666666-6666-6666-6666-666666666666"),
        current_user=make_current_user(
            role=UserRole.PROFESSOR,
            user_id=PROFESSOR_ID,
        ),
        command=UpdateClassroomCommand(
            name="AI 심화",
            professor_ids=[SECOND_PROFESSOR_ID],
            student_ids=[],
            allow_student_material_access=True,
        ),
    )

    assert classroom.name == "AI 심화"
    assert classroom.professor_ids == [SECOND_PROFESSOR_ID, PROFESSOR_ID]
    assert classroom.student_ids == []
    assert classroom.allow_student_material_access is True


@pytest.mark.asyncio
async def test_update_classroom_duplicate_schedule_raises():
    another_classroom = Classroom(
        organization_id=ORG_ID,
        name="데이터 과학",
        professor_ids=[SECOND_PROFESSOR_ID],
        grade=2,
        semester="2학기",
        section="02",
        description=None,
        student_ids=[],
        allow_student_material_access=False,
    )
    another_classroom.id = uuid4()
    service = make_service([make_classroom(), another_classroom])

    with pytest.raises(ClassroomAlreadyExistsException):
        await service.update_classroom(
            classroom_id=another_classroom.id,
            current_user=make_current_user(
                role=UserRole.PROFESSOR,
                user_id=SECOND_PROFESSOR_ID,
            ),
            command=UpdateClassroomCommand(
                name="AI 기초",
                grade=3,
                semester="1학기",
                section="01",
            ),
        )


@pytest.mark.asyncio
async def test_update_classroom_forbidden_for_non_manager_professor():
    service = make_service([make_classroom()])

    with pytest.raises(AuthForbiddenException):
        await service.update_classroom(
            classroom_id=UUID("66666666-6666-6666-6666-666666666666"),
            current_user=make_current_user(
                role=UserRole.PROFESSOR,
                user_id=SECOND_PROFESSOR_ID,
            ),
            command=UpdateClassroomCommand(name="AI 심화"),
        )


@pytest.mark.asyncio
async def test_invite_classroom_students_success():
    service = make_service([make_classroom()])

    classroom = await service.invite_classroom_students(
        classroom_id=UUID("66666666-6666-6666-6666-666666666666"),
        current_user=make_current_user(
            role=UserRole.PROFESSOR,
            user_id=PROFESSOR_ID,
        ),
        command=InviteClassroomStudentsCommand(student_ids=[SECOND_STUDENT_ID]),
    )

    assert classroom.student_ids == [STUDENT_ID, SECOND_STUDENT_ID]


@pytest.mark.asyncio
async def test_invite_classroom_students_duplicate_raises():
    service = make_service([make_classroom()])

    with pytest.raises(ClassroomStudentAlreadyInvitedException):
        await service.invite_classroom_students(
            classroom_id=UUID("66666666-6666-6666-6666-666666666666"),
            current_user=make_current_user(
                role=UserRole.PROFESSOR,
                user_id=PROFESSOR_ID,
            ),
            command=InviteClassroomStudentsCommand(student_ids=[STUDENT_ID]),
        )


@pytest.mark.asyncio
async def test_remove_classroom_student_success():
    classroom = make_classroom()
    classroom.student_ids = [STUDENT_ID, SECOND_STUDENT_ID]
    service = make_service([classroom])

    updated_classroom = await service.remove_classroom_student(
        classroom_id=classroom.id,
        current_user=make_current_user(
            role=UserRole.PROFESSOR,
            user_id=PROFESSOR_ID,
        ),
        command=RemoveClassroomStudentCommand(student_id=SECOND_STUDENT_ID),
    )

    assert updated_classroom.student_ids == [STUDENT_ID]


@pytest.mark.asyncio
async def test_remove_classroom_student_not_enrolled_raises():
    service = make_service([make_classroom()])

    with pytest.raises(ClassroomStudentNotEnrolledException):
        await service.remove_classroom_student(
            classroom_id=UUID("66666666-6666-6666-6666-666666666666"),
            current_user=make_current_user(
                role=UserRole.PROFESSOR,
                user_id=PROFESSOR_ID,
            ),
            command=RemoveClassroomStudentCommand(student_id=SECOND_STUDENT_ID),
        )


@pytest.mark.asyncio
async def test_delete_classroom_success():
    classroom = make_classroom()
    repository = InMemoryClassroomRepository([classroom])
    service = ClassroomService(
        repository=repository,
        user_repository=InMemoryUserRepository([
            make_user(PROFESSOR_ID, UserRole.PROFESSOR),
            make_user(SECOND_PROFESSOR_ID, UserRole.PROFESSOR),
            make_user(STUDENT_ID, UserRole.STUDENT),
            make_user(SECOND_STUDENT_ID, UserRole.STUDENT),
        ]),
    )

    deleted_classroom = await service.delete_classroom(
        classroom_id=classroom.id,
        current_user=make_current_user(role=UserRole.ADMIN, user_id=uuid4()),
    )

    assert deleted_classroom.id == classroom.id
    assert classroom.id not in repository.classrooms
