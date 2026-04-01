from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from app.auth.application.exception import AuthForbiddenException
from app.classroom.application.exception import (
    ClassroomAlreadyExistsException,
    ClassroomMaterialNotFoundException,
    ClassroomNotFoundException,
    ClassroomStudentAlreadyInvitedException,
    ClassroomStudentNotEnrolledException,
)
from app.classroom.application.service import ClassroomService
from app.classroom.domain.entity import (
    Classroom,
    ClassroomMaterialIngestStatus,
)
from app.user.adapter.output.persistence.sqlalchemy import (
    UserSQLAlchemyRepository,
)
from app.user.domain.entity import User, UserRole
from core.config import config
from core.domain.types import TokenType
from core.helpers.token import TokenHelper
from main import create_app

ORG_ID = UUID("11111111-1111-1111-1111-111111111111")
PROFESSOR_ID = UUID("22222222-2222-2222-2222-222222222222")
STUDENT_ID = UUID("33333333-3333-3333-3333-333333333333")
OTHER_PROFESSOR_ID = UUID("44444444-4444-4444-4444-444444444444")
SECOND_STUDENT_ID = UUID("55555555-5555-5555-5555-555555555555")
ADMIN_ID = UUID("66666666-6666-6666-6666-666666666666")
OTHER_ORG_ID = UUID("99999999-9999-9999-9999-999999999999")


@pytest.fixture
def client() -> TestClient:
    return TestClient(create_app())


def make_classroom(
    *,
    professor_ids: list[UUID] | None = None,
    student_ids: list[UUID] | None = None,
    allow_student_material_access: bool = False,
) -> Classroom:
    classroom = Classroom(
        organization_id=ORG_ID,
        name="AI 기초",
        professor_ids=professor_ids or [PROFESSOR_ID],
        grade=3,
        semester="1학기",
        section="01",
        description="AI 입문 강의실",
        student_ids=student_ids or [STUDENT_ID],
        allow_student_material_access=allow_student_material_access,
    )
    classroom.id = UUID("77777777-7777-7777-7777-777777777777")
    return classroom


def make_classroom_material_result():
    return SimpleNamespace(
        material=SimpleNamespace(
            id=UUID("99999999-9999-9999-9999-999999999999"),
            classroom_id=make_classroom().id,
            title="1주차 자료",
            week=1,
            description="소개 자료",
            uploaded_by=PROFESSOR_ID,
            created_at=None,
            ingest_status=ClassroomMaterialIngestStatus.PENDING,
            ingest_error=None,
            get_scope_candidates=lambda: [],
        ),
        file=SimpleNamespace(
            id=UUID("88888888-8888-8888-8888-888888888888"),
            file_name="week1.pdf",
            file_path="classrooms/materials/week1.pdf",
            file_extension="pdf",
            file_size=10,
            mime_type="application/pdf",
        ),
    )


def make_user(
    *,
    role: UserRole = UserRole.STUDENT,
    user_id: UUID = STUDENT_ID,
    organization_id: UUID = ORG_ID,
) -> User:
    user = User(
        organization_id=organization_id,
        login_id="user01",
        role=role,
        email="user@example.com",
        name="사용자",
    )
    user.id = user_id
    return user


def set_access_token_cookie(client: TestClient, user: User) -> None:
    access_token = TokenHelper.create_token(
        payload={"sub": str(user.id)},
        token_type=TokenType.ACCESS,
    )
    client.cookies.set(config.ACCESS_TOKEN_COOKIE_NAME, access_token)


def test_list_classrooms_returns_only_accessible_classrooms(
    client, monkeypatch
):
    async def list_stub_classrooms(*_args, **_kwargs):
        return [
            make_classroom(
                student_ids=[STUDENT_ID],
                allow_student_material_access=True,
            )
        ]

    current_user = make_user()

    async def get_by_id_stub(*_args, **_kwargs):
        return current_user

    monkeypatch.setattr(
        ClassroomService, "list_classrooms", list_stub_classrooms
    )
    monkeypatch.setattr(UserSQLAlchemyRepository, "get_by_id", get_by_id_stub)
    set_access_token_cookie(client, current_user)

    response = client.get("/api/classrooms")

    assert response.status_code == 200
    assert len(response.json()["data"]) == 1
    assert response.json()["data"][0]["name"] == "AI 기초"
    assert response.json()["data"][0]["allow_student_material_access"] is True


def test_list_classrooms_requires_login(client):
    response = client.get("/api/classrooms")

    assert response.status_code == 401
    assert response.json()["error_code"] == "AUTH__UNAUTHORIZED"


def test_create_classroom_returns_200_for_professor(client, monkeypatch):
    async def create_stub_classroom(*_args, **_kwargs):
        return make_classroom(
            professor_ids=[PROFESSOR_ID, OTHER_PROFESSOR_ID],
            allow_student_material_access=True,
        )

    professor_user = make_user(role=UserRole.PROFESSOR, user_id=PROFESSOR_ID)

    async def get_by_id_stub(*_args, **_kwargs):
        return professor_user

    monkeypatch.setattr(
        ClassroomService, "create_classroom", create_stub_classroom
    )
    monkeypatch.setattr(UserSQLAlchemyRepository, "get_by_id", get_by_id_stub)
    set_access_token_cookie(client, professor_user)

    response = client.post(
        "/api/classrooms",
        json={
            "name": "AI 기초",
            "professor_ids": [str(OTHER_PROFESSOR_ID)],
            "grade": 3,
            "semester": "1학기",
            "section": "01",
            "description": "AI 입문 강의실",
            "student_ids": [str(STUDENT_ID)],
            "allow_student_material_access": True,
        },
    )

    assert response.status_code == 200
    assert response.json()["data"]["professor_ids"] == [
        str(PROFESSOR_ID),
        str(OTHER_PROFESSOR_ID),
    ]
    assert response.json()["data"]["allow_student_material_access"] is True


def test_create_classroom_returns_403_for_student(client, monkeypatch):
    student_user = make_user(role=UserRole.STUDENT)

    async def get_by_id_stub(*_args, **_kwargs):
        return student_user

    monkeypatch.setattr(UserSQLAlchemyRepository, "get_by_id", get_by_id_stub)
    set_access_token_cookie(client, student_user)

    response = client.post(
        "/api/classrooms",
        json={
            "name": "AI 기초",
            "professor_ids": [str(PROFESSOR_ID)],
            "grade": 3,
            "semester": "1학기",
            "section": "01",
            "student_ids": [str(STUDENT_ID)],
        },
    )

    assert response.status_code == 403
    assert response.json()["error_code"] == "AUTH__FORBIDDEN"


def test_get_classroom_returns_403_for_other_organization(client, monkeypatch):
    async def raise_forbidden(*_args, **_kwargs):
        raise AuthForbiddenException()

    other_org_user = make_user(organization_id=OTHER_ORG_ID)

    async def get_by_id_stub(*_args, **_kwargs):
        return other_org_user

    monkeypatch.setattr(ClassroomService, "get_classroom", raise_forbidden)
    monkeypatch.setattr(UserSQLAlchemyRepository, "get_by_id", get_by_id_stub)
    set_access_token_cookie(client, other_org_user)

    response = client.get(f"/api/classrooms/{make_classroom().id}")

    assert response.status_code == 403
    assert response.json()["error_code"] == "AUTH__FORBIDDEN"


def test_update_classroom_returns_200_for_professor_member(client, monkeypatch):
    async def update_stub_classroom(*_args, **_kwargs):
        classroom = make_classroom(allow_student_material_access=True)
        classroom.name = "AI 심화"
        return classroom

    professor_user = make_user(role=UserRole.PROFESSOR, user_id=PROFESSOR_ID)

    async def get_by_id_stub(*_args, **_kwargs):
        return professor_user

    monkeypatch.setattr(
        ClassroomService, "update_classroom", update_stub_classroom
    )
    monkeypatch.setattr(UserSQLAlchemyRepository, "get_by_id", get_by_id_stub)
    set_access_token_cookie(client, professor_user)

    response = client.patch(
        f"/api/classrooms/{make_classroom().id}",
        json={"name": "AI 심화", "allow_student_material_access": True},
    )

    assert response.status_code == 200
    assert response.json()["data"]["name"] == "AI 심화"
    assert response.json()["data"]["allow_student_material_access"] is True


def test_update_classroom_returns_403_for_non_member_professor(
    client,
    monkeypatch,
):
    async def raise_forbidden(*_args, **_kwargs):
        raise AuthForbiddenException()

    professor_user = make_user(
        role=UserRole.PROFESSOR,
        user_id=OTHER_PROFESSOR_ID,
    )

    async def get_by_id_stub(*_args, **_kwargs):
        return professor_user

    monkeypatch.setattr(ClassroomService, "update_classroom", raise_forbidden)
    monkeypatch.setattr(UserSQLAlchemyRepository, "get_by_id", get_by_id_stub)
    set_access_token_cookie(client, professor_user)

    response = client.patch(
        f"/api/classrooms/{make_classroom().id}",
        json={"name": "AI 심화"},
    )

    assert response.status_code == 403
    assert response.json()["error_code"] == "AUTH__FORBIDDEN"


def test_invite_classroom_students_returns_200(client, monkeypatch):
    async def invite_stub_students(*_args, **_kwargs):
        return make_classroom(student_ids=[STUDENT_ID, SECOND_STUDENT_ID])

    professor_user = make_user(role=UserRole.PROFESSOR, user_id=PROFESSOR_ID)

    async def get_by_id_stub(*_args, **_kwargs):
        return professor_user

    monkeypatch.setattr(
        ClassroomService,
        "invite_classroom_students",
        invite_stub_students,
    )
    monkeypatch.setattr(UserSQLAlchemyRepository, "get_by_id", get_by_id_stub)
    set_access_token_cookie(client, professor_user)

    response = client.post(
        f"/api/classrooms/{make_classroom().id}/students",
        json={"student_ids": [str(SECOND_STUDENT_ID)]},
    )

    assert response.status_code == 200
    assert response.json()["data"]["student_ids"] == [
        str(STUDENT_ID),
        str(SECOND_STUDENT_ID),
    ]


def test_invite_classroom_students_returns_409_for_duplicate(
    client,
    monkeypatch,
):
    async def raise_duplicate(*_args, **_kwargs):
        raise ClassroomStudentAlreadyInvitedException()

    professor_user = make_user(role=UserRole.PROFESSOR, user_id=PROFESSOR_ID)

    async def get_by_id_stub(*_args, **_kwargs):
        return professor_user

    monkeypatch.setattr(
        ClassroomService,
        "invite_classroom_students",
        raise_duplicate,
    )
    monkeypatch.setattr(UserSQLAlchemyRepository, "get_by_id", get_by_id_stub)
    set_access_token_cookie(client, professor_user)

    response = client.post(
        f"/api/classrooms/{make_classroom().id}/students",
        json={"student_ids": [str(STUDENT_ID)]},
    )

    assert response.status_code == 409
    assert response.json()["error_code"] == "CLASSROOM__STUDENT_ALREADY_INVITED"


def test_remove_classroom_student_returns_200(client, monkeypatch):
    async def remove_stub_student(*_args, **_kwargs):
        return make_classroom(student_ids=[STUDENT_ID])

    admin_user = make_user(role=UserRole.ADMIN, user_id=ADMIN_ID)

    async def get_by_id_stub(*_args, **_kwargs):
        return admin_user

    monkeypatch.setattr(
        ClassroomService,
        "remove_classroom_student",
        remove_stub_student,
    )
    monkeypatch.setattr(UserSQLAlchemyRepository, "get_by_id", get_by_id_stub)
    set_access_token_cookie(client, admin_user)

    response = client.delete(
        f"/api/classrooms/{make_classroom().id}/students/{STUDENT_ID}"
    )

    assert response.status_code == 200
    assert response.json()["data"]["student_ids"] == [str(STUDENT_ID)]


def test_remove_classroom_student_returns_404_for_missing_membership(
    client,
    monkeypatch,
):
    async def raise_not_enrolled(*_args, **_kwargs):
        raise ClassroomStudentNotEnrolledException()

    admin_user = make_user(role=UserRole.ADMIN, user_id=ADMIN_ID)

    async def get_by_id_stub(*_args, **_kwargs):
        return admin_user

    monkeypatch.setattr(
        ClassroomService,
        "remove_classroom_student",
        raise_not_enrolled,
    )
    monkeypatch.setattr(UserSQLAlchemyRepository, "get_by_id", get_by_id_stub)
    set_access_token_cookie(client, admin_user)

    response = client.delete(
        f"/api/classrooms/{make_classroom().id}/students/{SECOND_STUDENT_ID}"
    )

    assert response.status_code == 404
    assert response.json()["error_code"] == "CLASSROOM__STUDENT_NOT_ENROLLED"


def test_delete_classroom_returns_200_for_admin(client, monkeypatch):
    async def delete_stub_classroom(*_args, **_kwargs):
        return make_classroom()

    admin_user = make_user(role=UserRole.ADMIN, user_id=ADMIN_ID)

    async def get_by_id_stub(*_args, **_kwargs):
        return admin_user

    monkeypatch.setattr(
        ClassroomService, "delete_classroom", delete_stub_classroom
    )
    monkeypatch.setattr(UserSQLAlchemyRepository, "get_by_id", get_by_id_stub)
    set_access_token_cookie(client, admin_user)

    response = client.delete(f"/api/classrooms/{make_classroom().id}")

    assert response.status_code == 200
    assert response.json()["data"]["name"] == "AI 기초"


def test_create_classroom_duplicate_returns_409(client, monkeypatch):
    async def raise_duplicate_classroom(*_args, **_kwargs):
        raise ClassroomAlreadyExistsException()

    professor_user = make_user(role=UserRole.PROFESSOR, user_id=PROFESSOR_ID)

    async def get_by_id_stub(*_args, **_kwargs):
        return professor_user

    monkeypatch.setattr(
        ClassroomService,
        "create_classroom",
        raise_duplicate_classroom,
    )
    monkeypatch.setattr(UserSQLAlchemyRepository, "get_by_id", get_by_id_stub)
    set_access_token_cookie(client, professor_user)

    response = client.post(
        "/api/classrooms",
        json={
            "name": "AI 기초",
            "professor_ids": [str(PROFESSOR_ID)],
            "grade": 3,
            "semester": "1학기",
            "section": "01",
            "student_ids": [str(STUDENT_ID)],
        },
    )

    assert response.status_code == 409
    assert response.json()["error_code"] == "CLASSROOM__ALREADY_EXISTS"


def test_get_classroom_not_found_returns_404(client, monkeypatch):
    async def raise_not_found(*_args, **_kwargs):
        raise ClassroomNotFoundException()

    current_user = make_user()

    async def get_by_id_stub(*_args, **_kwargs):
        return current_user

    monkeypatch.setattr(ClassroomService, "get_classroom", raise_not_found)
    monkeypatch.setattr(UserSQLAlchemyRepository, "get_by_id", get_by_id_stub)
    set_access_token_cookie(client, current_user)

    response = client.get(f"/api/classrooms/{uuid4()}")

    assert response.status_code == 404
    assert response.json()["error_code"] == "CLASSROOM__NOT_FOUND"


def test_create_classroom_invalid_input_returns_422(client, monkeypatch):
    professor_user = make_user(role=UserRole.PROFESSOR, user_id=PROFESSOR_ID)

    async def get_by_id_stub(*_args, **_kwargs):
        return professor_user

    monkeypatch.setattr(UserSQLAlchemyRepository, "get_by_id", get_by_id_stub)
    set_access_token_cookie(client, professor_user)

    response = client.post(
        "/api/classrooms",
        json={
            "name": "A",
            "professor_ids": [],
            "grade": 0,
            "semester": "",
            "section": "",
        },
    )

    assert response.status_code == 422
    assert response.json()["error_code"] == "SERVER__REQUEST_VALIDATION_ERROR"


def test_invite_classroom_students_invalid_input_returns_422(
    client, monkeypatch
):
    professor_user = make_user(role=UserRole.PROFESSOR, user_id=PROFESSOR_ID)

    async def get_by_id_stub(*_args, **_kwargs):
        return professor_user

    monkeypatch.setattr(UserSQLAlchemyRepository, "get_by_id", get_by_id_stub)
    set_access_token_cookie(client, professor_user)

    response = client.post(
        f"/api/classrooms/{make_classroom().id}/students",
        json={"student_ids": []},
    )

    assert response.status_code == 422
    assert response.json()["error_code"] == "SERVER__REQUEST_VALIDATION_ERROR"


def test_update_classroom_empty_patch_returns_422(client, monkeypatch):
    professor_user = make_user(role=UserRole.PROFESSOR, user_id=PROFESSOR_ID)

    async def get_by_id_stub(*_args, **_kwargs):
        return professor_user

    monkeypatch.setattr(UserSQLAlchemyRepository, "get_by_id", get_by_id_stub)
    set_access_token_cookie(client, professor_user)

    response = client.patch(f"/api/classrooms/{make_classroom().id}", json={})

    assert response.status_code == 422
    assert response.json()["error_code"] == "SERVER__REQUEST_VALIDATION_ERROR"


def test_list_classroom_materials_returns_200(client, monkeypatch):
    async def list_stub_materials(*_args, **_kwargs):
        return [make_classroom_material_result()]

    current_user = make_user()

    async def get_by_id_stub(*_args, **_kwargs):
        return current_user

    monkeypatch.setattr(
        ClassroomService,
        "list_classroom_materials",
        list_stub_materials,
    )
    monkeypatch.setattr(UserSQLAlchemyRepository, "get_by_id", get_by_id_stub)
    set_access_token_cookie(client, current_user)

    response = client.get(f"/api/classrooms/{make_classroom().id}/materials")

    assert response.status_code == 200
    assert response.json()["data"][0]["title"] == "1주차 자료"
    assert response.json()["data"][0]["file"]["file_name"] == "week1.pdf"


def test_get_classroom_material_not_found_returns_404(client, monkeypatch):
    async def raise_not_found(*_args, **_kwargs):
        raise ClassroomMaterialNotFoundException()

    current_user = make_user()

    async def get_by_id_stub(*_args, **_kwargs):
        return current_user

    monkeypatch.setattr(
        ClassroomService,
        "get_classroom_material",
        raise_not_found,
    )
    monkeypatch.setattr(UserSQLAlchemyRepository, "get_by_id", get_by_id_stub)
    set_access_token_cookie(client, current_user)

    response = client.get(
        f"/api/classrooms/{make_classroom().id}/materials/99999999-9999-9999-9999-999999999999"
    )

    assert response.status_code == 404
    assert response.json()["error_code"] == "CLASSROOM_MATERIAL__NOT_FOUND"
