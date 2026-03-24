from dataclasses import dataclass

import httpx
import pytest

from app.auth.adapter.output.integration import HansungIdentityVerifier
from app.auth.application.exception import (
    AuthIdentityProviderNotConfiguredException,
    AuthIdentityProviderUnavailableException,
    AuthInvalidCredentialsException,
)
from app.organization.domain.entity import (
    Organization,
    OrganizationAuthProvider,
)
from core.config import config


@dataclass
class FakeResponse:
    status_code: int = 200
    text: str = ""


class FakeAsyncClient:
    def __init__(
        self, *, post_response: FakeResponse, get_response: FakeResponse
    ):
        self.post_response = post_response
        self.get_response = get_response
        self.post_calls: list[tuple[str, dict[str, str]]] = []
        self.get_calls: list[str] = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        del exc_type, exc, tb
        return False

    async def post(self, url: str, data: dict[str, str]) -> FakeResponse:
        self.post_calls.append((url, data))
        return self.post_response

    async def get(self, url: str) -> FakeResponse:
        self.get_calls.append(url)
        return self.get_response


def fake_async_client_factory(fake_client: FakeAsyncClient):
    def factory(**_kwargs):
        return fake_client

    return factory


class TimeoutAsyncClient:
    def __init__(self, **_kwargs):
        pass

    async def __aenter__(self):
        raise httpx.TimeoutException("timeout")

    async def __aexit__(self, exc_type, exc, tb):
        del exc_type, exc, tb
        return False


def make_organization(
    provider: OrganizationAuthProvider = OrganizationAuthProvider.HANSUNG_SIS,
) -> Organization:
    return Organization(
        code="hansung",
        name="Hansung University",
        auth_provider=provider,
    )


@pytest.mark.asyncio
async def test_verify_returns_student_identity(monkeypatch):
    fake_client = FakeAsyncClient(
        post_response=FakeResponse(text="로그인 성공"),
        get_response=FakeResponse(text="홍길동님 학생 포털"),
    )

    monkeypatch.setattr(
        "app.auth.adapter.output.integration.hansung.httpx.AsyncClient",
        fake_async_client_factory(fake_client),
    )

    verifier = HansungIdentityVerifier()
    identity = await verifier.verify(
        organization=make_organization(),
        login_id="20260001",
        password="secret",
    )

    assert identity.login_id == "20260001"
    assert identity.name == "홍길동"
    assert identity.role.value == "student"
    assert fake_client.post_calls == [
        (
            config.HANSUNG_LOGIN_URL,
            {
                "id": "20260001",
                "password": "secret",
                "changePass": "",
                "return_url": "null",
            },
        )
    ]
    assert fake_client.get_calls == [config.HANSUNG_INFO_URL]


@pytest.mark.asyncio
async def test_verify_returns_professor_identity(monkeypatch):
    fake_client = FakeAsyncClient(
        post_response=FakeResponse(text="로그인 성공"),
        get_response=FakeResponse(text="김교수님 교수 업무 시스템"),
    )

    monkeypatch.setattr(
        "app.auth.adapter.output.integration.hansung.httpx.AsyncClient",
        fake_async_client_factory(fake_client),
    )

    verifier = HansungIdentityVerifier()
    identity = await verifier.verify(
        organization=make_organization(),
        login_id="prof001",
        password="secret",
    )

    assert identity.name == "김교수"
    assert identity.role.value == "professor"


@pytest.mark.asyncio
async def test_verify_raises_invalid_credentials_for_login_page(monkeypatch):
    fake_client = FakeAsyncClient(
        post_response=FakeResponse(text="로그인 폼입니다"),
        get_response=FakeResponse(
            text=(
                '<form action="gong_login"><input name="password" />'
                '<input name="changePass" /></form>'
            )
        ),
    )

    monkeypatch.setattr(
        "app.auth.adapter.output.integration.hansung.httpx.AsyncClient",
        fake_async_client_factory(fake_client),
    )

    verifier = HansungIdentityVerifier()

    with pytest.raises(AuthInvalidCredentialsException):
        await verifier.verify(
            organization=make_organization(),
            login_id="20260001",
            password="wrong-secret",
        )


@pytest.mark.asyncio
async def test_verify_raises_provider_unavailable_on_timeout(monkeypatch):
    monkeypatch.setattr(
        "app.auth.adapter.output.integration.hansung.httpx.AsyncClient",
        TimeoutAsyncClient,
    )

    verifier = HansungIdentityVerifier()

    with pytest.raises(AuthIdentityProviderUnavailableException):
        await verifier.verify(
            organization=make_organization(),
            login_id="20260001",
            password="secret",
        )


@pytest.mark.asyncio
async def test_verify_raises_when_provider_is_not_hansung():
    organization = make_organization()
    organization.auth_provider = "other"
    verifier = HansungIdentityVerifier()

    with pytest.raises(AuthIdentityProviderNotConfiguredException):
        await verifier.verify(
            organization=organization,
            login_id="20260001",
            password="secret",
        )
