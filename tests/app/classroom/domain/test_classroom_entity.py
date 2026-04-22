from uuid import UUID, uuid4

import pytest

from app.auth.domain.entity import CurrentUser
from app.classroom.domain.entity import (
    Classroom,
    ClassroomMaterial,
    ClassroomMaterialIngestCapability,
    ClassroomMaterialIngestStatus,
    ClassroomMaterialOriginalFile,
)
from app.classroom.domain.exception import (
    ClassroomInvalidProfessorRoleDomainException,
    ClassroomProfessorNotFoundDomainException,
)
from app.user.domain.entity import User, UserRole

ORG_ID = UUID("11111111-1111-1111-1111-111111111111")
PROFESSOR_ID = UUID("22222222-2222-2222-2222-222222222222")
SECOND_PROFESSOR_ID = UUID("33333333-3333-3333-3333-333333333333")
STUDENT_ID = UUID("44444444-4444-4444-4444-444444444444")
SECOND_STUDENT_ID = UUID("55555555-5555-5555-5555-555555555555")


def make_classroom() -> Classroom:
    return Classroom(
        organization_id=ORG_ID,
        name="AI 기초",
        professor_ids=[PROFESSOR_ID],
        grade=3,
        semester="1학기",
        section="01",
        description="AI 입문 강의실",
        student_ids=[STUDENT_ID],
    )


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


def test_classroom_entity_contains_multiple_professors_and_students():
    classroom = make_classroom()

    assert classroom.name == "AI 기초"
    assert classroom.professor_ids == [PROFESSOR_ID]
    assert classroom.student_ids == [STUDENT_ID]


def test_merge_professor_ids_includes_current_professor_once():
    classroom = make_classroom()

    merged_professor_ids = classroom.merge_professor_ids(
        [SECOND_PROFESSOR_ID, SECOND_PROFESSOR_ID],
        current_user=make_current_user(
            role=UserRole.PROFESSOR,
            user_id=PROFESSOR_ID,
        ),
    )

    assert merged_professor_ids == [SECOND_PROFESSOR_ID, PROFESSOR_ID]


def test_update_details_normalizes_student_ids_and_updates_fields():
    classroom = make_classroom()

    classroom.update_details(
        name="AI 심화",
        grade=4,
        semester="2학기",
        section="02",
        description=None,
        replace_description=True,
        allow_student_material_access=True,
        replace_allow_student_material_access=True,
        professor_ids=[SECOND_PROFESSOR_ID],
        student_ids=[SECOND_STUDENT_ID, SECOND_STUDENT_ID],
    )

    assert classroom.name == "AI 심화"
    assert classroom.grade == 4
    assert classroom.semester == "2학기"
    assert classroom.section == "02"
    assert classroom.description is None
    assert classroom.allow_student_material_access is True
    assert classroom.professor_ids == [SECOND_PROFESSOR_ID]
    assert classroom.student_ids == [SECOND_STUDENT_ID]


def test_invited_student_ids_deduplicates_new_students():
    classroom = make_classroom()

    invited_student_ids = classroom.invited_student_ids([
        SECOND_STUDENT_ID,
        SECOND_STUDENT_ID,
    ])

    assert invited_student_ids == [STUDENT_ID, SECOND_STUDENT_ID]


def test_remove_student_returns_false_when_student_is_missing():
    classroom = make_classroom()

    removed = classroom.remove_student(SECOND_STUDENT_ID)

    assert removed is False
    assert classroom.student_ids == [STUDENT_ID]


def test_can_be_accessed_by_returns_true_for_enrolled_student():
    classroom = make_classroom()

    can_access = classroom.can_be_accessed_by(
        make_current_user(role=UserRole.STUDENT, user_id=STUDENT_ID)
    )

    assert can_access is True


def test_can_be_accessed_by_returns_false_for_other_organization_user():
    classroom = make_classroom()

    can_access = classroom.can_be_accessed_by(
        CurrentUser(
            id=uuid4(),
            organization_id=uuid4(),
            login_id="other-user",
            role=UserRole.ADMIN,
        )
    )

    assert can_access is False


def test_create_classroom_factory_normalizes_professors_and_students():
    classroom = Classroom.create(
        organization_id=ORG_ID,
        name="AI 기초",
        professor_ids=[SECOND_PROFESSOR_ID, SECOND_PROFESSOR_ID],
        current_user=make_current_user(
            role=UserRole.PROFESSOR,
            user_id=PROFESSOR_ID,
        ),
        grade=3,
        semester="1학기",
        section="01",
        description="AI 입문 강의실",
        student_ids=[STUDENT_ID, STUDENT_ID],
        allow_student_material_access=False,
    )

    assert classroom.professor_ids == [SECOND_PROFESSOR_ID, PROFESSOR_ID]
    assert classroom.student_ids == [STUDENT_ID]


def test_classroom_material_factory_and_update_rules():
    material = ClassroomMaterial.create_file(
        classroom_id=uuid4(),
        file_id=uuid4(),
        title="1주차 자료",
        week=1,
        description="소개 자료",
        uploaded_by=PROFESSOR_ID,
        original_file=ClassroomMaterialOriginalFile(
            file_name="week1.pdf",
            file_path="classrooms/materials/week1.pdf",
            file_extension="pdf",
            file_size=10,
            mime_type="application/pdf",
        ),
        ingest_capability=ClassroomMaterialIngestCapability(
            supported=True,
            reason=None,
        ),
    )
    replacement_file_id = uuid4()

    material.update(
        title="수정 자료",
        week=2,
        description=None,
        replace_description=True,
    )
    old_file_id = material.replace_file(
        file_id=replacement_file_id,
        original_file=ClassroomMaterialOriginalFile(
            file_name="week2.pdf",
            file_path="classrooms/materials/week2.pdf",
            file_extension="pdf",
            file_size=20,
            mime_type="application/pdf",
        ),
        ingest_capability=ClassroomMaterialIngestCapability(
            supported=True,
            reason=None,
        ),
    )

    assert material.title == "수정 자료"
    assert material.week == 2
    assert material.description is None
    assert material.ingest_status is ClassroomMaterialIngestStatus.PENDING
    assert old_file_id != replacement_file_id
    assert material.file_id == replacement_file_id


def test_validate_members_raises_when_professor_is_missing():
    classroom = make_classroom()

    with pytest.raises(ClassroomProfessorNotFoundDomainException):
        classroom.validate_members({
            STUDENT_ID: make_user(STUDENT_ID, UserRole.STUDENT)
        })


def test_validate_members_raises_when_professor_role_is_invalid():
    classroom = make_classroom()

    with pytest.raises(ClassroomInvalidProfessorRoleDomainException):
        classroom.validate_members({
            PROFESSOR_ID: make_user(PROFESSOR_ID, UserRole.STUDENT),
            STUDENT_ID: make_user(STUDENT_ID, UserRole.STUDENT),
        })
