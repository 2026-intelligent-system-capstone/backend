from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from app.user.application.exception import (
    UserAccountAlreadyExistsException,
    UserNotFoundException,
)
from app.user.application.service.user import UserService
from app.user.domain.entity.user import Profile, User, UserRole
from main import create_app

ORGANIZATION_ID = UUID("11111111-1111-1111-1111-111111111111")


@pytest.fixture
def client() -> TestClient:
    app = create_app()
    return TestClient(app)


def make_user(
    login_id: str = "20260001",
    email: str | None = "test@example.com",
) -> User:
    return User(
        organization_id=ORGANIZATION_ID,
        login_id=login_id,
        role=UserRole.STUDENT,
        email=email,
        profile=Profile(
            nickname="tester",
            name="김테스트",
            phone_number="010-1234-5678",
        ),
    )


def test_create_user_returns_serialized_id(client, monkeypatch):
    async def create_stub_user(*_args, **_kwargs):
        return make_user()

    monkeypatch.setattr(UserService, "create_user", create_stub_user)

    response = client.post(
        "/api/users",
        json={
            "organization_id": str(ORGANIZATION_ID),
            "login_id": "20260001",
            "role": "student",
            "email": "test@example.com",
            "nickname": "tester",
            "name": "김테스트",
            "phone_number": "010-1234-5678",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert isinstance(body["data"]["id"], str)
    assert body["data"]["login_id"] == "20260001"


def test_list_users_returns_200(client, monkeypatch):
    async def list_stub_users(*_args, **_kwargs):
        return [
            make_user(login_id="20260001", email="first@example.com"),
            make_user(login_id="20260002", email="second@example.com"),
        ]

    monkeypatch.setattr(UserService, "list_users", list_stub_users)

    response = client.get("/api/users")

    assert response.status_code == 200
    body = response.json()
    assert len(body["data"]) == 2
    assert body["data"][0]["login_id"] == "20260001"


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

    monkeypatch.setattr(UserService, "update_user", update_stub_user)

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


def test_delete_user_returns_200(client, monkeypatch):
    async def delete_stub_user(*_args, **_kwargs):
        user = make_user()
        user.delete()
        return user

    monkeypatch.setattr(UserService, "delete_user", delete_stub_user)

    response = client.delete(f"/api/users/{uuid4()}")

    assert response.status_code == 200
    assert response.json()["data"]["is_deleted"] is True


def test_create_user_duplicate_account_returns_409(client, monkeypatch):
    async def raise_duplicate_account(*_args, **_kwargs):
        raise UserAccountAlreadyExistsException()

    monkeypatch.setattr(UserService, "create_user", raise_duplicate_account)

    response = client.post(
        "/api/users",
        json={
            "organization_id": str(ORGANIZATION_ID),
            "login_id": "20260001",
            "role": "student",
            "email": "dup@example.com",
            "nickname": "tester",
            "name": "김테스트",
            "phone_number": "010-1234-5678",
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
                "nickname": "tester",
                "name": "김테스트",
                "phone_number": "010-1234-5678",
            },
            "login_id",
        ),
        (
            {
                "organization_id": "invalid-uuid",
                "login_id": "20260001",
                "role": "student",
                "email": "user@example.com",
                "nickname": "tester",
                "name": "김테스트",
                "phone_number": "010-1234-5678",
            },
            "organization_id",
        ),
        (
            {
                "organization_id": str(ORGANIZATION_ID),
                "login_id": "20260001",
                "role": "unknown",
                "email": "user@example.com",
                "nickname": "tester",
                "name": "김테스트",
                "phone_number": "010-1234-5678",
            },
            "role",
        ),
        (
            {
                "organization_id": str(ORGANIZATION_ID),
                "login_id": "20260001",
                "role": "student",
                "email": "invalid-email",
                "nickname": "tester",
                "name": "김테스트",
                "phone_number": "010-1234-5678",
            },
            "email",
        ),
        (
            {
                "organization_id": str(ORGANIZATION_ID),
                "login_id": "20260001",
                "role": "student",
                "email": "user@example.com",
                "nickname": "t",
                "name": "김테스트",
                "phone_number": "010-1234-5678",
            },
            "nickname",
        ),
        (
            {
                "organization_id": str(ORGANIZATION_ID),
                "login_id": "20260001",
                "role": "student",
                "email": "user@example.com",
                "nickname": "tester",
                "name": "김",
                "phone_number": "010-1234-5678",
            },
            "name",
        ),
    ],
)
def test_create_user_invalid_input_returns_422(client, payload, field_name):
    response = client.post("/api/users", json=payload)

    assert response.status_code == 422
    body = response.json()
    assert body["error_code"] == "SERVER__REQUEST_VALIDATION_ERROR"
    assert any(
        field_name in ".".join(map(str, item["loc"]))
        or field_name in item["msg"]
        for item in body["detail"]
    )
