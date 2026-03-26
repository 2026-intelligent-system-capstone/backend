from dataclasses import dataclass
from typing import cast

import httpx
import pytest

from app.auth.application.exception import (
    AuthIdentityProviderNotConfiguredException,
    AuthIdentityProviderUnavailableException,
    AuthInvalidCredentialsException,
)
from app.organization.adapter.output.integration import HansungAuthService
from app.organization.domain.entity import (
    Organization,
    OrganizationAuthProvider,
)


@dataclass
class FakeResponse:
    status_code: int = 200
    text: str = ""
    headers: dict[str, str] | None = None
    url: str = "https://info.hansung.ac.kr/h_dae/dae_main.html"

    def __post_init__(self):
        if self.headers is None:
            self.headers = {}


class FakeAsyncClient:
    def __init__(
        self,
        *,
        post_response: FakeResponse,
        portal_response: FakeResponse,
        identity_response: FakeResponse | None = None,
    ):
        service = HansungAuthService()
        self.post_response = post_response
        self.portal_response = portal_response
        self.identity_response = identity_response or FakeResponse(
            status_code=portal_response.status_code,
            text=portal_response.text,
            headers=dict(portal_response.headers or {}),
            url=portal_response.url,
        )
        self.portal_response.url = service.config.portal_url
        self.identity_response.url = service.config.responsive_index_url
        self.root_response = FakeResponse(text="login page")
        self.root_response.url = service.config.login_page_url
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

    async def get(
        self,
        url: str,
        follow_redirects: bool = False,
    ) -> FakeResponse:
        del follow_redirects
        self.get_calls.append(url)
        service = HansungAuthService()
        if url == service.config.login_page_url:
            return self.root_response
        if url == service.config.responsive_index_url:
            return self.identity_response
        return self.portal_response


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
        code="univ_hansung",
        name="한성대학교",
        auth_provider=provider,
    )


@pytest.mark.asyncio
async def test_authenticate_returns_student_identity(monkeypatch):
    fake_client = FakeAsyncClient(
        post_response=FakeResponse(
            status_code=302,
            headers={
                "location": ("https://info.hansung.ac.kr/h_dae/dae_main.html")
            },
        ),
        portal_response=FakeResponse(text="portal page"),
        identity_response=FakeResponse(
            text="""
            <div class="info">
                <a href="/jsp_21/index.jsp" class="d-block">
                    웹공학트랙<br/> 지능시스템트랙<br/> 홍길동
                </a>
            </div>
            학생 메뉴
            """,
        ),
    )

    monkeypatch.setattr(
        "app.organization.adapter.output.integration.hansung.httpx.AsyncClient",
        fake_async_client_factory(fake_client),
    )

    service = HansungAuthService()
    identity = await service.authenticate(
        organization=make_organization(),
        login_id="20260001",
        password="secret",
    )

    assert identity.login_id == "20260001"
    assert identity.name == "홍길동"
    assert identity.role.value == "student"
    assert fake_client.post_calls == [
        (
            service.config.login_url,
            {
                "id": "20260001",
                "passwd": "secret",
                "changePass": "",
                "return_url": "null",
            },
        )
    ]
    assert fake_client.get_calls == [
        service.config.login_page_url,
        service.config.portal_url,
        service.config.responsive_index_url,
    ]


@pytest.mark.asyncio
async def test_authenticate_returns_professor_identity(monkeypatch):
    fake_client = FakeAsyncClient(
        post_response=FakeResponse(
            status_code=302,
            headers={
                "location": ("https://info.hansung.ac.kr/h_dae/dae_main.html")
            },
        ),
        portal_response=FakeResponse(text="portal page"),
        identity_response=FakeResponse(
            text="""
            <div class="info">
                <a href="/jsp_21/index.jsp" class="d-block">
                    교수지원<br/> 김교수
                </a>
            </div>
            교수 업무 시스템
            """,
        ),
    )

    monkeypatch.setattr(
        "app.organization.adapter.output.integration.hansung.httpx.AsyncClient",
        fake_async_client_factory(fake_client),
    )

    service = HansungAuthService()
    identity = await service.authenticate(
        organization=make_organization(),
        login_id="prof001",
        password="secret",
    )

    assert identity.name == "김교수"
    assert identity.role.value == "professor"


@pytest.mark.asyncio
async def test_authenticate_falls_back_when_portal_has_no_identity_text(
    monkeypatch,
):
    fake_client = FakeAsyncClient(
        post_response=FakeResponse(
            status_code=302,
            headers={
                "location": "https://info.hansung.ac.kr/h_dae/dae_main.html"
            },
        ),
        portal_response=FakeResponse(text="<html><body>portal</body></html>"),
    )

    monkeypatch.setattr(
        "app.organization.adapter.output.integration.hansung.httpx.AsyncClient",
        fake_async_client_factory(fake_client),
    )

    service = HansungAuthService()
    identity = await service.authenticate(
        organization=make_organization(),
        login_id="2071396",
        password="secret",
    )

    assert identity.name == "2071396"
    assert identity.role.value == "student"


@pytest.mark.asyncio
async def test_authenticate_raises_invalid_credentials_for_login_page(
    monkeypatch,
):
    fake_client = FakeAsyncClient(
        post_response=FakeResponse(
            status_code=302,
            headers={
                "location": ("https://info.hansung.ac.kr/h_dae/dae_main.html")
            },
        ),
        portal_response=FakeResponse(
            text="portal page",
            headers={},
        ),
    )

    fake_client.portal_response.url = "https://info.hansung.ac.kr/"

    monkeypatch.setattr(
        "app.organization.adapter.output.integration.hansung.httpx.AsyncClient",
        fake_async_client_factory(fake_client),
    )

    service = HansungAuthService()

    with pytest.raises(AuthInvalidCredentialsException):
        await service.authenticate(
            organization=make_organization(),
            login_id="20260001",
            password="wrong-secret",
        )


@pytest.mark.asyncio
async def test_authenticate_rejects_non_redirect_login_response(
    monkeypatch,
):
    fake_client = FakeAsyncClient(
        post_response=FakeResponse(status_code=200, text="login failed"),
        portal_response=FakeResponse(text="홍길동님 학생 포털"),
    )

    monkeypatch.setattr(
        "app.organization.adapter.output.integration.hansung.httpx.AsyncClient",
        fake_async_client_factory(fake_client),
    )

    service = HansungAuthService()

    with pytest.raises(AuthInvalidCredentialsException):
        await service.authenticate(
            organization=make_organization(),
            login_id="20260001",
            password="wrong-secret",
        )


@pytest.mark.asyncio
async def test_authenticate_rejects_wrong_redirect_target(monkeypatch):
    fake_client = FakeAsyncClient(
        post_response=FakeResponse(
            status_code=302,
            headers={
                "location": (
                    "https://info.hansung.ac.kr/jsp/sugang/"
                    "h_sugang_sincheong_main.jsp"
                )
            },
        ),
        portal_response=FakeResponse(text="portal page"),
    )

    monkeypatch.setattr(
        "app.organization.adapter.output.integration.hansung.httpx.AsyncClient",
        fake_async_client_factory(fake_client),
    )

    service = HansungAuthService()

    with pytest.raises(AuthInvalidCredentialsException):
        await service.authenticate(
            organization=make_organization(),
            login_id="20260001",
            password="wrong-secret",
        )


@pytest.mark.asyncio
async def test_authenticate_raises_provider_unavailable_on_timeout(
    monkeypatch,
):
    monkeypatch.setattr(
        "app.organization.adapter.output.integration.hansung.httpx.AsyncClient",
        TimeoutAsyncClient,
    )

    service = HansungAuthService()

    with pytest.raises(AuthIdentityProviderUnavailableException):
        await service.authenticate(
            organization=make_organization(),
            login_id="20260001",
            password="secret",
        )


@pytest.mark.asyncio
async def test_authenticate_raises_when_provider_is_not_hansung():
    organization = make_organization()
    organization.auth_provider = cast(OrganizationAuthProvider, "other")
    service = HansungAuthService()

    with pytest.raises(AuthIdentityProviderNotConfiguredException):
        await service.authenticate(
            organization=organization,
            login_id="20260001",
            password="secret",
        )
