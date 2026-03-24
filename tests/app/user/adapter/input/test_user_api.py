from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.user.application.exception import (
    UserEmailAlreadyExistsException,
    UserNameAlreadyExistsException,
    UserNotFoundException,
)
from app.user.application.service.user import UserService
from app.user.domain.entity.user import Profile, User
from main import create_app


@pytest.fixture
def client() -> TestClient:
    app = create_app()
    return TestClient(app)


def make_user(
    username: str = "testuser", email: str = "test@example.com"
) -> User:
    return User(
        username=username,
        password="hashed_password",
        email=email,
        profile=Profile(
            nickname="tester",
            real_name="김테스트",
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
            "username": "testuser",
            "password": "secure_password123",
            "email": "test@example.com",
            "nickname": "tester",
            "real_name": "김테스트",
            "phone_number": "010-1234-5678",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert isinstance(body["data"]["id"], str)
    assert body["data"]["email"] == "test@example.com"


def test_list_users_returns_200(client, monkeypatch):
    async def list_stub_users(*_args, **_kwargs):
        return [
            make_user(username="first", email="first@example.com"),
            make_user(username="second", email="second@example.com"),
        ]

    monkeypatch.setattr(UserService, "list_users", list_stub_users)

    response = client.get("/api/users")

    assert response.status_code == 200
    body = response.json()
    assert len(body["data"]) == 2
    assert body["data"][0]["username"] == "first"


def test_get_user_returns_200(client, monkeypatch):
    async def get_stub_user(*_args, **_kwargs):
        return make_user()

    monkeypatch.setattr(UserService, "get_user", get_stub_user)

    response = client.get(f"/api/users/{uuid4()}")

    assert response.status_code == 200
    assert response.json()["data"]["username"] == "testuser"


def test_get_user_not_found_returns_404(client, monkeypatch):
    async def raise_not_found(*_args, **_kwargs):
        raise UserNotFoundException()

    monkeypatch.setattr(UserService, "get_user", raise_not_found)

    response = client.get(f"/api/users/{uuid4()}")

    assert response.status_code == 404
    assert response.json()["error_code"] == "USER__NOT_FOUND"


def test_update_user_returns_200(client, monkeypatch):
    async def update_stub_user(*_args, **_kwargs):
        return make_user(username="updated_user", email="updated@example.com")

    monkeypatch.setattr(UserService, "update_user", update_stub_user)

    response = client.patch(
        f"/api/users/{uuid4()}",
        json={
            "nickname": "updated",
            "real_name": "김업데이트",
        },
    )

    assert response.status_code == 200
    assert response.json()["data"]["username"] == "updated_user"


def test_delete_user_returns_200(client, monkeypatch):
    async def delete_stub_user(*_args, **_kwargs):
        user = make_user()
        user.delete()
        return user

    monkeypatch.setattr(UserService, "delete_user", delete_stub_user)

    response = client.delete(f"/api/users/{uuid4()}")

    assert response.status_code == 200
    assert response.json()["data"]["is_deleted"] is True


def test_create_user_duplicate_username_returns_400(client, monkeypatch):
    async def raise_duplicate_username(*_args, **_kwargs):
        raise UserNameAlreadyExistsException()

    monkeypatch.setattr(UserService, "create_user", raise_duplicate_username)

    response = client.post(
        "/api/users",
        json={
            "username": "duplicate_user",
            "password": "secure_password123",
            "email": "dup-user@example.com",
            "nickname": "tester",
            "real_name": "김테스트",
            "phone_number": "010-1234-5678",
        },
    )

    assert response.status_code == 409
    assert response.json()["error_code"] == "USER__USERNAME_ALREADY_EXISTS"


def test_create_user_duplicate_email_returns_400(client, monkeypatch):
    async def raise_duplicate_email(*_args, **_kwargs):
        raise UserEmailAlreadyExistsException()

    monkeypatch.setattr(UserService, "create_user", raise_duplicate_email)

    response = client.post(
        "/api/users",
        json={
            "username": "testuser",
            "password": "secure_password123",
            "email": "dup@example.com",
            "nickname": "tester",
            "real_name": "김테스트",
            "phone_number": "010-1234-5678",
        },
    )

    assert response.status_code == 409
    assert response.json()["error_code"] == "USER__EMAIL_ALREADY_EXISTS"


@pytest.mark.parametrize(
    ("payload", "field_name"),
    [
        (
            {
                "username": "usr",
                "password": "secure_password123",
                "email": "user@example.com",
                "nickname": "tester",
                "real_name": "김테스트",
                "phone_number": "010-1234-5678",
            },
            "username",
        ),
        (
            {
                "username": "testuser",
                "password": "short",
                "email": "user@example.com",
                "nickname": "tester",
                "real_name": "김테스트",
                "phone_number": "010-1234-5678",
            },
            "password",
        ),
        (
            {
                "username": "testuser",
                "password": "secure_password123",
                "email": "invalid-email",
                "nickname": "tester",
                "real_name": "김테스트",
                "phone_number": "010-1234-5678",
            },
            "email",
        ),
        (
            {
                "username": "testuser",
                "password": "secure_password123",
                "email": "user@example.com",
                "nickname": "t",
                "real_name": "김테스트",
                "phone_number": "010-1234-5678",
            },
            "nickname",
        ),
        (
            {
                "username": "testuser",
                "password": "secure_password123",
                "email": "user@example.com",
                "nickname": "tester",
                "real_name": "김",
                "phone_number": "010-1234-5678",
            },
            "real_name",
        ),
        (
            {
                "username": "testuser",
                "password": "secure_password123",
                "email": "user@example.com",
                "nickname": "tester",
                "real_name": "김테스트",
                "phone_number": "01012345678",
            },
            "phone_number",
        ),
        (
            {
                "username": "testuser",
                "password": "secure_password123",
                "email": "user@example.com",
                "nickname": "tester",
                "phone_number": "010-1234-5678",
            },
            "real_name",
        ),
    ],
)
def test_create_user_invalid_input_returns_422(client, payload, field_name):
    response = client.post("/api/users", json=payload)

    assert response.status_code == 422
    body = response.json()
    assert body["error_code"] == "SERVER__REQUEST_VALIDATION_ERROR"
    assert any(
        field_name in ".".join(map(str, item["loc"])) for item in body["detail"]
    )


def test_update_user_invalid_input_returns_422(client):
    response = client.patch(f"/api/users/{uuid4()}", json={})

    assert response.status_code == 422
    assert response.json()["error_code"] == "SERVER__REQUEST_VALIDATION_ERROR"
