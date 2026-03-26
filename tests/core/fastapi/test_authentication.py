from types import SimpleNamespace
from uuid import UUID

import pytest
from starlette.requests import HTTPConnection

from app.auth.domain.entity import RequestUser
from core.domain.types import TokenType
from core.fastapi.authentication import CookieAuthBackend
from core.helpers.token import TokenHelper

USER_ID = UUID("11111111-1111-1111-1111-111111111111")


def make_connection(cookies: dict[str, str] | None = None) -> HTTPConnection:
    cookie_header = b""
    if cookies:
        cookie_header = "; ".join(
            f"{key}={value}" for key, value in cookies.items()
        ).encode()

    return HTTPConnection({
        "type": "http",
        "headers": [(b"cookie", cookie_header)] if cookie_header else [],
        "app": SimpleNamespace(),
    })


@pytest.mark.asyncio
async def test_cookie_auth_backend_returns_none_without_access_cookie():
    backend = CookieAuthBackend()

    result = await backend.authenticate(make_connection())

    assert result is None


@pytest.mark.asyncio
async def test_cookie_auth_backend_authenticates_valid_access_token():
    backend = CookieAuthBackend()
    access_token = TokenHelper.create_token(
        payload={"sub": str(USER_ID)},
        token_type=TokenType.ACCESS,
    )

    result = await backend.authenticate(
        make_connection({"access_token": access_token})
    )

    assert result is not None
    credentials, user = result
    assert credentials.scopes == ["authenticated"]
    assert user == RequestUser(id=USER_ID)


@pytest.mark.asyncio
async def test_cookie_auth_backend_rejects_refresh_token_cookie():
    backend = CookieAuthBackend()
    refresh_token = TokenHelper.create_token(
        payload={"sub": str(USER_ID), "jti": "refresh-jti"},
        token_type=TokenType.REFRESH,
    )

    result = await backend.authenticate(
        make_connection({"access_token": refresh_token})
    )

    assert result is None


@pytest.mark.asyncio
async def test_cookie_auth_backend_rejects_invalid_user_id_payload():
    backend = CookieAuthBackend()
    access_token = TokenHelper.create_token(
        payload={"sub": "not-a-uuid"},
        token_type=TokenType.ACCESS,
    )

    result = await backend.authenticate(
        make_connection({"access_token": access_token})
    )

    assert result is None
