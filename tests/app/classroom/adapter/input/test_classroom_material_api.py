from datetime import datetime
from io import BytesIO
from uuid import UUID

import pytest
from fastapi.testclient import TestClient

from app.auth.application.exception import AuthForbiddenException
from app.classroom.application.exception import (
    ClassroomMaterialNotFoundException,
)
from app.classroom.application.service import ClassroomService
from app.file.domain.entity.file import File, FileStatus
from app.user.adapter.output.persistence.sqlalchemy import (
    UserSQLAlchemyRepository,
)
from app.user.domain.entity import User, UserRole
from core.config import config
from core.domain.types import TokenType
from core.helpers.token import TokenHelper
from main import create_app

ORG_ID = UUID("11111111-1111-1111-1111-111111111111")
CLASSROOM_ID = UUID("22222222-2222-2222-2222-222222222222")
PROFESSOR_ID = UUID("33333333-3333-3333-3333-333333333333")
STUDENT_ID = UUID("44444444-4444-4444-4444-444444444444")
MATERIAL_ID = UUID("55555555-5555-5555-5555-555555555555")
FILE_ID = UUID("66666666-6666-6666-6666-666666666666")


@pytest.fixture
def client() -> TestClient:
    return TestClient(create_app())


def make_user(*, role: UserRole, user_id: UUID) -> User:
    user = User(
        organization_id=ORG_ID,
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


def make_result():
    file = File(
        file_name="week1.pdf",
        file_path="classrooms/week1.pdf",
        file_extension="pdf",
        file_size=10,
        mime_type="application/pdf",
        status=FileStatus.ACTIVE,
    )
    file.id = FILE_ID

    material = type("Material", (), {})()
    material.id = MATERIAL_ID
    material.classroom_id = CLASSROOM_ID
    material.title = "1주차 자료"
    material.week = 1
    material.description = "소개 자료"
    material.uploaded_by = PROFESSOR_ID
    material.created_at = datetime(2026, 1, 1, 9, 0, 0)

    result = type("Result", (), {})()
    result.material = material
    result.file = file
    return result


def test_create_classroom_material_returns_200_for_professor(
    client,
    monkeypatch,
):
    async def create_stub(*_args, **_kwargs):
        return make_result()

    professor_user = make_user(role=UserRole.PROFESSOR, user_id=PROFESSOR_ID)

    async def get_by_id_stub(*_args, **_kwargs):
        return professor_user

    monkeypatch.setattr(
        ClassroomService,
        "create_classroom_material",
        create_stub,
    )
    monkeypatch.setattr(UserSQLAlchemyRepository, "get_by_id", get_by_id_stub)
    set_access_token_cookie(client, professor_user)

    response = client.post(
        f"/api/classrooms/{CLASSROOM_ID}/materials",
        data={
            "title": "1주차 자료",
            "week": "1",
            "description": "소개 자료",
        },
        files={
            "uploaded_file": (
                "week1.pdf",
                BytesIO(b"pdf-content"),
                "application/pdf",
            )
        },
    )

    assert response.status_code == 200
    assert response.json()["data"]["title"] == "1주차 자료"
    assert response.json()["data"]["file"]["file_name"] == "week1.pdf"


def test_create_classroom_material_returns_403_for_student(
    client,
    monkeypatch,
):
    student_user = make_user(role=UserRole.STUDENT, user_id=STUDENT_ID)

    async def get_by_id_stub(*_args, **_kwargs):
        return student_user

    monkeypatch.setattr(UserSQLAlchemyRepository, "get_by_id", get_by_id_stub)
    set_access_token_cookie(client, student_user)

    response = client.post(
        f"/api/classrooms/{CLASSROOM_ID}/materials",
        data={"title": "1주차 자료", "week": "1"},
        files={
            "uploaded_file": (
                "week1.pdf",
                BytesIO(b"pdf-content"),
                "application/pdf",
            )
        },
    )

    assert response.status_code == 403
    assert response.json()["error_code"] == "AUTH__FORBIDDEN"


def test_list_classroom_materials_returns_200_for_student(
    client,
    monkeypatch,
):
    async def list_stub(*_args, **_kwargs):
        return [make_result()]

    student_user = make_user(role=UserRole.STUDENT, user_id=STUDENT_ID)

    async def get_by_id_stub(*_args, **_kwargs):
        return student_user

    monkeypatch.setattr(
        ClassroomService,
        "list_classroom_materials",
        list_stub,
    )
    monkeypatch.setattr(UserSQLAlchemyRepository, "get_by_id", get_by_id_stub)
    set_access_token_cookie(client, student_user)

    response = client.get(f"/api/classrooms/{CLASSROOM_ID}/materials")

    assert response.status_code == 200
    assert len(response.json()["data"]) == 1
    assert response.json()["data"][0]["week"] == 1


def test_get_classroom_material_returns_403_when_forbidden(
    client,
    monkeypatch,
):
    async def raise_forbidden(*_args, **_kwargs):
        raise AuthForbiddenException()

    student_user = make_user(role=UserRole.STUDENT, user_id=STUDENT_ID)

    async def get_by_id_stub(*_args, **_kwargs):
        return student_user

    monkeypatch.setattr(
        ClassroomService,
        "get_classroom_material",
        raise_forbidden,
    )
    monkeypatch.setattr(UserSQLAlchemyRepository, "get_by_id", get_by_id_stub)
    set_access_token_cookie(client, student_user)

    response = client.get(
        f"/api/classrooms/{CLASSROOM_ID}/materials/{MATERIAL_ID}"
    )

    assert response.status_code == 403
    assert response.json()["error_code"] == "AUTH__FORBIDDEN"


def test_update_classroom_material_returns_200_for_professor(
    client,
    monkeypatch,
):
    async def update_stub(*_args, **_kwargs):
        result = make_result()
        result.material.title = "수정 자료"
        return result

    professor_user = make_user(role=UserRole.PROFESSOR, user_id=PROFESSOR_ID)

    async def get_by_id_stub(*_args, **_kwargs):
        return professor_user

    monkeypatch.setattr(
        ClassroomService,
        "update_classroom_material",
        update_stub,
    )
    monkeypatch.setattr(UserSQLAlchemyRepository, "get_by_id", get_by_id_stub)
    set_access_token_cookie(client, professor_user)

    response = client.patch(
        f"/api/classrooms/{CLASSROOM_ID}/materials/{MATERIAL_ID}",
        data={"title": "수정 자료"},
    )

    assert response.status_code == 200
    assert response.json()["data"]["title"] == "수정 자료"


def test_delete_classroom_material_returns_200_for_professor(
    client,
    monkeypatch,
):
    async def delete_stub(*_args, **_kwargs):
        return make_result()

    professor_user = make_user(role=UserRole.PROFESSOR, user_id=PROFESSOR_ID)

    async def get_by_id_stub(*_args, **_kwargs):
        return professor_user

    monkeypatch.setattr(
        ClassroomService,
        "delete_classroom_material",
        delete_stub,
    )
    monkeypatch.setattr(UserSQLAlchemyRepository, "get_by_id", get_by_id_stub)
    set_access_token_cookie(client, professor_user)

    response = client.delete(
        f"/api/classrooms/{CLASSROOM_ID}/materials/{MATERIAL_ID}"
    )

    assert response.status_code == 200
    assert response.json()["data"]["id"] == str(MATERIAL_ID)


def test_get_classroom_material_not_found_returns_404(client, monkeypatch):
    async def raise_not_found(*_args, **_kwargs):
        raise ClassroomMaterialNotFoundException()

    student_user = make_user(role=UserRole.STUDENT, user_id=STUDENT_ID)

    async def get_by_id_stub(*_args, **_kwargs):
        return student_user

    monkeypatch.setattr(
        ClassroomService,
        "get_classroom_material",
        raise_not_found,
    )
    monkeypatch.setattr(UserSQLAlchemyRepository, "get_by_id", get_by_id_stub)
    set_access_token_cookie(client, student_user)

    response = client.get(
        f"/api/classrooms/{CLASSROOM_ID}/materials/{MATERIAL_ID}"
    )

    assert response.status_code == 404
    assert response.json()["error_code"] == "CLASSROOM_MATERIAL__NOT_FOUND"


def test_create_classroom_material_invalid_payload_returns_422(
    client,
    monkeypatch,
):
    professor_user = make_user(role=UserRole.PROFESSOR, user_id=PROFESSOR_ID)

    async def get_by_id_stub(*_args, **_kwargs):
        return professor_user

    monkeypatch.setattr(UserSQLAlchemyRepository, "get_by_id", get_by_id_stub)
    set_access_token_cookie(client, professor_user)

    response = client.post(
        f"/api/classrooms/{CLASSROOM_ID}/materials",
        data={"title": "", "week": "0"},
        files={
            "uploaded_file": (
                "week1.pdf",
                BytesIO(b"pdf-content"),
                "application/pdf",
            )
        },
    )

    assert response.status_code == 422
    assert response.json()["error_code"] == "SERVER__REQUEST_VALIDATION_ERROR"


def test_update_classroom_material_empty_patch_returns_422(
    client,
    monkeypatch,
):
    professor_user = make_user(role=UserRole.PROFESSOR, user_id=PROFESSOR_ID)

    async def get_by_id_stub(*_args, **_kwargs):
        return professor_user

    monkeypatch.setattr(UserSQLAlchemyRepository, "get_by_id", get_by_id_stub)
    set_access_token_cookie(client, professor_user)

    response = client.patch(
        f"/api/classrooms/{CLASSROOM_ID}/materials/{MATERIAL_ID}",
        data={},
    )

    assert response.status_code == 422
    assert response.json()["error_code"] == "SERVER__REQUEST_VALIDATION_ERROR"


def test_download_classroom_material_returns_stream_response(
    client,
    monkeypatch,
):
    async def download_stub(*_args, **_kwargs):
        return type(
            "FileDownload",
            (),
            {
                "file_name": "week1.pdf",
                "mime_type": "application/pdf",
                "content": BytesIO(b"pdf-content"),
            },
        )()

    student_user = make_user(role=UserRole.STUDENT, user_id=STUDENT_ID)

    async def get_by_id_stub(*_args, **_kwargs):
        return student_user

    monkeypatch.setattr(
        ClassroomService,
        "get_classroom_material_download",
        download_stub,
    )
    monkeypatch.setattr(UserSQLAlchemyRepository, "get_by_id", get_by_id_stub)
    set_access_token_cookie(client, student_user)

    response = client.get(
        f"/api/classrooms/{CLASSROOM_ID}/materials/{MATERIAL_ID}/download"
    )

    assert response.status_code == 200
    assert response.content == b"pdf-content"
    assert response.headers["content-type"] == "application/pdf"
    assert (
        response.headers["content-disposition"]
        == 'attachment; filename="week1.pdf"'
    )
