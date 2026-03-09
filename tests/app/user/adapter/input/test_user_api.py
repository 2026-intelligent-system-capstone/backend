import pytest
from fastapi.testclient import TestClient

from app.user.application.exceptions.user import UserEmailAlreadyExistsException
from app.user.application.service.user import UserService
from main import create_app


@pytest.fixture
def client() -> TestClient:
    app = create_app()
    return TestClient(app)


def test_create_user_returns_serialized_id(client, monkeypatch):
    async def create_stub_user(*_args, **_kwargs):
        from app.user.domain.entity.user import Profile, User

        return User(
            username="testuser",
            password="hashed_password",
            email="test@example.com",
            profile=Profile(nickname="tester", real_name="김테스트", phone_number="010-1234-5678"),
        )

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

    assert response.status_code == 400
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
    assert any(field_name in ".".join(map(str, item["loc"])) for item in body["detail"])
