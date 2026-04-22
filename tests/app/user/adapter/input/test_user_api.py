from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from app.user.adapter.output.persistence.sqlalchemy import (
    UserSQLAlchemyRepository,
)
from app.user.application.exception import (
    UserAccountAlreadyExistsException,
    UserNotFoundException,
)
from app.user.application.service import UserService
from app.user.domain.entity import User, UserRole
from core.config import config
from core.domain.types import TokenType
from core.helpers.token import TokenHelper
from main import create_app

ORGANIZATION_ID = UUID("11111111-1111-1111-1111-111111111111")


@pytest.fixture
def client() -> TestClient:
    app = create_app()
    return TestClient(app)


def make_user(
    login_id: str = "20260001",
    email: str | None = "test@example.com",
    role: UserRole = UserRole.STUDENT,
) -> User:
    return User(
        organization_id=ORGANIZATION_ID,
        login_id=login_id,
        role=role,
        email=email,
        name="김테스트",
    )


def set_access_token_cookie(client: TestClient, user: User) -> None:
    access_token = TokenHelper.create_token(
        payload={"sub": str(user.id)},
        token_type=TokenType.ACCESS,
    )
    client.cookies.set(config.ACCESS_TOKEN_COOKIE_NAME, access_token)


def test_create_user_returns_serialized_id(client, monkeypatch):
    async def create_stub_user(*_args, **_kwargs):
        return make_user()

    admin_user = make_user(login_id="admin01", role=UserRole.ADMIN)

    async def get_by_id_stub(*_args, **_kwargs):
        return admin_user

    monkeypatch.setattr(UserService, "create_user", create_stub_user)
    monkeypatch.setattr(UserSQLAlchemyRepository, "get_by_id", get_by_id_stub)
    set_access_token_cookie(client, admin_user)

    response = client.post(
        "/api/users",
        json={
            "organization_id": str(ORGANIZATION_ID),
            "login_id": "20260001",
            "role": "student",
            "email": "test@example.com",
            "name": "김테스트",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert isinstance(body["data"]["id"], str)
    assert body["data"]["login_id"] == "20260001"


def test_create_user_returns_403_for_non_admin(client, monkeypatch):
    student_user = make_user(role=UserRole.STUDENT)

    async def get_by_id_stub(*_args, **_kwargs):
        return student_user

    monkeypatch.setattr(UserSQLAlchemyRepository, "get_by_id", get_by_id_stub)
    set_access_token_cookie(client, student_user)

    response = client.post(
        "/api/users",
        json={
            "organization_id": str(ORGANIZATION_ID),
            "login_id": "20260001",
            "role": "student",
            "email": "test@example.com",
            "name": "김테스트",
        },
    )

    assert response.status_code == 403
    assert response.json()["error_code"] == "AUTH__FORBIDDEN"


def test_list_users_returns_401_without_access_token(client):
    response = client.get("/api/users")

    assert response.status_code == 401
    assert response.json()["error_code"] == "AUTH__UNAUTHORIZED"


def test_list_users_returns_401_with_invalid_access_token(client):
    client.cookies.set(config.ACCESS_TOKEN_COOKIE_NAME, "invalid-token")

    response = client.get("/api/users")

    assert response.status_code == 401
    assert response.json()["error_code"] == "AUTH__UNAUTHORIZED"


def test_list_users_returns_200(client, monkeypatch):
    async def list_stub_users(*_args, **_kwargs):
        return [
            make_user(login_id="20260001", email="first@example.com"),
            make_user(login_id="20260002", email="second@example.com"),
        ]

    authenticated_user = make_user()

    async def get_by_id_stub(*_args, **_kwargs):
        return authenticated_user

    monkeypatch.setattr(UserService, "list_users", list_stub_users)
    monkeypatch.setattr(UserSQLAlchemyRepository, "get_by_id", get_by_id_stub)
    set_access_token_cookie(client, authenticated_user)

    response = client.get("/api/users")

    assert response.status_code == 200
    body = response.json()
    assert len(body["data"]) == 2
    assert body["data"][0]["login_id"] == "20260001"


def test_get_me_returns_200(client, monkeypatch):
    authenticated_user = make_user(login_id="20261111", email="me@example.com")

    async def get_by_id_stub(*_args, **_kwargs):
        return authenticated_user

    async def get_stub_user(*_args, **_kwargs):
        return authenticated_user

    monkeypatch.setattr(UserSQLAlchemyRepository, "get_by_id", get_by_id_stub)
    monkeypatch.setattr(UserService, "get_user", get_stub_user)
    set_access_token_cookie(client, authenticated_user)

    response = client.get("/api/users/me")

    assert response.status_code == 200
    body = response.json()
    assert body["data"]["id"] == str(authenticated_user.id)
    assert body["data"]["login_id"] == "20261111"


def test_get_me_returns_401_without_access_token(client):
    response = client.get("/api/users/me")

    assert response.status_code == 401
    assert response.json()["error_code"] == "AUTH__UNAUTHORIZED"


def test_get_me_returns_401_with_invalid_access_token(client):
    client.cookies.set(config.ACCESS_TOKEN_COOKIE_NAME, "invalid-token")

    response = client.get("/api/users/me")

    assert response.status_code == 401
    assert response.json()["error_code"] == "AUTH__UNAUTHORIZED"


def test_get_user_returns_200(client, monkeypatch):
    async def get_stub_user(*_args, **_kwargs):
        return make_user()

    monkeypatch.setattr(UserService, "get_user", get_stub_user)

    response = client.get(f"/api/users/{uuid4()}")

    assert response.status_code == 200
    assert response.json()["data"]["login_id"] == "20260001"


def test_get_user_not_found_returns_404(client, monkeypatch):
    async def raise_not_found(*_args, **_kwargs):
        raise UserNotFoundException()

    monkeypatch.setattr(UserService, "get_user", raise_not_found)

    response = client.get(f"/api/users/{uuid4()}")

    assert response.status_code == 404
    assert response.json()["error_code"] == "USER__NOT_FOUND"


def test_update_user_returns_200(client, monkeypatch):
    async def update_stub_user(*_args, **_kwargs):
        user = make_user(login_id="20269999", email="updated@example.com")
        user.role = UserRole.PROFESSOR
        return user

    admin_user = make_user(login_id="admin01", role=UserRole.ADMIN)

    async def get_by_id_stub(*_args, **_kwargs):
        return admin_user

    monkeypatch.setattr(UserService, "update_user", update_stub_user)
    monkeypatch.setattr(UserSQLAlchemyRepository, "get_by_id", get_by_id_stub)
    set_access_token_cookie(client, admin_user)

    response = client.patch(
        f"/api/users/{uuid4()}",
        json={
            "name": "김업데이트",
            "role": "professor",
        },
    )

    assert response.status_code == 200
    assert response.json()["data"]["login_id"] == "20269999"
    assert response.json()["data"]["role"] == "professor"


def test_update_user_returns_403_for_non_admin(client, monkeypatch):
    student_user = make_user(role=UserRole.STUDENT)

    async def get_by_id_stub(*_args, **_kwargs):
        return student_user

    monkeypatch.setattr(UserSQLAlchemyRepository, "get_by_id", get_by_id_stub)
    set_access_token_cookie(client, student_user)

    response = client.patch(
        f"/api/users/{uuid4()}",
        json={
            "name": "김업데이트",
            "role": "professor",
        },
    )

    assert response.status_code == 403
    assert response.json()["error_code"] == "AUTH__FORBIDDEN"


def test_delete_user_returns_200(client, monkeypatch):
    async def delete_stub_user(*_args, **_kwargs):
        user = make_user()
        user.delete()
        return user

    admin_user = make_user(login_id="admin01", role=UserRole.ADMIN)

    async def get_by_id_stub(*_args, **_kwargs):
        return admin_user

    monkeypatch.setattr(UserService, "delete_user", delete_stub_user)
    monkeypatch.setattr(UserSQLAlchemyRepository, "get_by_id", get_by_id_stub)
    set_access_token_cookie(client, admin_user)

    response = client.delete(f"/api/users/{uuid4()}")

    assert response.status_code == 200
    assert response.json()["data"]["is_deleted"] is True


def test_delete_user_returns_403_for_non_admin(client, monkeypatch):
    student_user = make_user(role=UserRole.STUDENT)

    async def get_by_id_stub(*_args, **_kwargs):
        return student_user

    monkeypatch.setattr(UserSQLAlchemyRepository, "get_by_id", get_by_id_stub)
    set_access_token_cookie(client, student_user)

    response = client.delete(f"/api/users/{uuid4()}")

    assert response.status_code == 403
    assert response.json()["error_code"] == "AUTH__FORBIDDEN"


def test_create_user_duplicate_account_returns_409(client, monkeypatch):
    async def raise_duplicate_account(*_args, **_kwargs):
        raise UserAccountAlreadyExistsException()

    admin_user = make_user(login_id="admin01", role=UserRole.ADMIN)

    async def get_by_id_stub(*_args, **_kwargs):
        return admin_user

    monkeypatch.setattr(UserService, "create_user", raise_duplicate_account)
    monkeypatch.setattr(UserSQLAlchemyRepository, "get_by_id", get_by_id_stub)
    set_access_token_cookie(client, admin_user)

    response = client.post(
        "/api/users",
        json={
            "organization_id": str(ORGANIZATION_ID),
            "login_id": "20260001",
            "role": "student",
            "email": "dup@example.com",
            "name": "김테스트",
        },
    )

    assert response.status_code == 409
    assert response.json()["error_code"] == "USER__ACCOUNT_ALREADY_EXISTS"


@pytest.mark.parametrize(
    ("payload", "field_name"),
    [
        (
            {
                "organization_id": str(ORGANIZATION_ID),
                "login_id": "",
                "role": "student",
                "email": "user@example.com",
                "name": "김테스트",
            },
            "login_id",
        ),
        (
            {
                "organization_id": "invalid-uuid",
                "login_id": "20260001",
                "role": "student",
                "email": "user@example.com",
                "name": "김테스트",
            },
            "organization_id",
        ),
        (
            {
                "organization_id": str(ORGANIZATION_ID),
                "login_id": "20260001",
                "role": "unknown",
                "email": "user@example.com",
                "name": "김테스트",
            },
            "role",
        ),
        (
            {
                "organization_id": str(ORGANIZATION_ID),
                "login_id": "20260001",
                "role": "student",
                "email": "invalid-email",
                "name": "김테스트",
            },
            "email",
        ),
        (
            {
                "organization_id": str(ORGANIZATION_ID),
                "login_id": "20260001",
                "role": "student",
                "email": "user@example.com",
                "name": "김",
            },
            "name",
        ),
    ],
)
def test_create_user_invalid_input_returns_422(
    client,
    monkeypatch,
    payload,
    field_name,
):
    admin_user = make_user(login_id="admin01", role=UserRole.ADMIN)

    async def get_by_id_stub(*_args, **_kwargs):
        return admin_user

    monkeypatch.setattr(UserSQLAlchemyRepository, "get_by_id", get_by_id_stub)
    set_access_token_cookie(client, admin_user)

    response = client.post("/api/users", json=payload)

    assert response.status_code == 422
    body = response.json()
    assert body["error_code"] == "SERVER__REQUEST_VALIDATION_ERROR"
    assert any(
        field_name in ".".join(map(str, item["loc"]))
        or field_name in item["msg"]
        for item in body["detail"]
    )
