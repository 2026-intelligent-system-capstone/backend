import pytest
from fastapi.testclient import TestClient

from app.auth.application.dto import AuthTokensDTO
from app.auth.application.exception import (
    AuthIdentityProviderNotConfiguredException,
    AuthIdentityProviderUnavailableException,
    AuthInvalidCredentialsException,
    AuthInvalidRefreshTokenException,
)
from app.auth.application.service import AuthService
from main import create_app


@pytest.fixture
def client() -> TestClient:
    return TestClient(create_app())


def make_tokens() -> AuthTokensDTO:
    return AuthTokensDTO(
        user_id="11111111-1111-1111-1111-111111111111",
        organization_id="22222222-2222-2222-2222-222222222222",
        organization_code="univ_hansung",
        role="student",
        access_token="access-token-value",
        refresh_token="refresh-token-value",
    )


def test_login_sets_auth_cookies(client, monkeypatch):
    async def login_stub(*_args, **_kwargs):
        return make_tokens()

    monkeypatch.setattr(AuthService, "login", login_stub)

    response = client.post(
        "/api/auth/login",
        json={
            "organization_code": "univ_hansung",
            "login_id": "20260001",
            "password": "secure_password123",
        },
    )

    assert response.status_code == 200
    assert response.json() is None
    assert response.cookies.get("access_token") == "access-token-value"
    assert response.cookies.get("refresh_token") == "refresh-token-value"


def test_login_invalid_credentials_returns_401(client, monkeypatch):
    async def login_stub(*_args, **_kwargs):
        raise AuthInvalidCredentialsException()

    monkeypatch.setattr(AuthService, "login", login_stub)

    response = client.post(
        "/api/auth/login",
        json={
            "organization_code": "univ_hansung",
            "login_id": "20260001",
            "password": "secure_password123",
        },
    )

    assert response.status_code == 401
    assert response.json()["error_code"] == "AUTH__INVALID_CREDENTIALS"


def test_login_provider_not_configured_returns_503(client, monkeypatch):
    async def login_stub(*_args, **_kwargs):
        raise AuthIdentityProviderNotConfiguredException()

    monkeypatch.setattr(AuthService, "login", login_stub)

    response = client.post(
        "/api/auth/login",
        json={
            "organization_code": "univ_hansung",
            "login_id": "20260001",
            "password": "secure_password123",
        },
    )

    assert response.status_code == 503
    assert (
        response.json()["error_code"]
        == "AUTH__IDENTITY_PROVIDER_NOT_CONFIGURED"
    )


def test_login_provider_unavailable_returns_503(client, monkeypatch):
    async def login_stub(*_args, **_kwargs):
        raise AuthIdentityProviderUnavailableException()

    monkeypatch.setattr(AuthService, "login", login_stub)

    response = client.post(
        "/api/auth/login",
        json={
            "organization_code": "univ_hansung",
            "login_id": "20260001",
            "password": "secure_password123",
        },
    )

    assert response.status_code == 503
    assert (
        response.json()["error_code"] == "AUTH__IDENTITY_PROVIDER_UNAVAILABLE"
    )


def test_refresh_rotates_auth_cookies(client, monkeypatch):
    async def refresh_stub(*_args, **_kwargs):
        return make_tokens()

    monkeypatch.setattr(AuthService, "refresh", refresh_stub)
    client.cookies.set("refresh_token", "old-refresh-token")

    response = client.post("/api/auth/refresh")

    assert response.status_code == 200
    assert response.json() is None
    assert response.cookies.get("access_token") == "access-token-value"
    assert response.cookies.get("refresh_token") == "refresh-token-value"


def test_refresh_without_cookie_returns_401(client):
    response = client.post("/api/auth/refresh")

    assert response.status_code == 401
    assert response.json()["error_code"] == "AUTH__INVALID_REFRESH_TOKEN"


def test_logout_clears_auth_cookies(client, monkeypatch):
    async def logout_stub(*_args, **_kwargs):
        return None

    monkeypatch.setattr(AuthService, "logout", logout_stub)
    client.cookies.set("refresh_token", "refresh-token-value")
    client.cookies.set("access_token", "access-token-value")

    response = client.post("/api/auth/logout")

    set_cookie_header = response.headers.get("set-cookie", "")
    assert response.status_code == 200
    assert response.json() is None
    assert "access_token=" in set_cookie_header
    assert "refresh_token=" in set_cookie_header


def test_refresh_invalid_token_returns_401(client, monkeypatch):
    async def refresh_stub(*_args, **_kwargs):
        raise AuthInvalidRefreshTokenException()

    monkeypatch.setattr(AuthService, "refresh", refresh_stub)
    client.cookies.set("refresh_token", "bad-refresh-token")

    response = client.post("/api/auth/refresh")

    assert response.status_code == 401
    assert response.json()["error_code"] == "AUTH__INVALID_REFRESH_TOKEN"
