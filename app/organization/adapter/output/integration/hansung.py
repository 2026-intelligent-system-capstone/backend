import re
from dataclasses import dataclass
from urllib.parse import urlparse

import httpx

from app.auth.application.exception import (
    AuthIdentityProviderNotConfiguredException,
    AuthIdentityProviderUnavailableException,
    AuthInvalidCredentialsException,
)
from app.organization.domain.entity import (
    Organization,
    OrganizationAuthProvider,
    OrganizationIdentity,
)
from app.organization.domain.service import OrganizationAuthService
from app.user.domain.entity import UserRole

LOGIN_REDIRECT_STATUS_CODE = 302

NAME_PATTERNS = (
    re.compile(r"([가-힣]{2,10})\s*님"),
    re.compile(r"성명\s*[:：]?\s*([가-힣A-Za-z ]{2,40})"),
    re.compile(r"이름\s*[:：]?\s*([가-힣A-Za-z ]{2,40})"),
    re.compile(
        r'<div class="info">.*?<a[^>]*class="d-block"[^>]*>(.*?)</a>',
        re.S,
    ),
)


@dataclass(frozen=True)
class HansungAuthConfig:
    login_url: str = "https://info.hansung.ac.kr/servlet/s_gong.gong_login_ssl"
    login_page_url: str = "https://info.hansung.ac.kr/"
    portal_url: str = "https://info.hansung.ac.kr/h_dae/dae_main.html"
    responsive_index_url: str = "https://info.hansung.ac.kr/jsp_21/index.jsp"
    referer_url: str = (
        "https://info.hansung.ac.kr/jsp/sugang/h_sugang_sincheong_main.jsp"
    )
    timeout_seconds: float = 10.0
    headers: dict[str, str] | None = None

    def resolved_headers(self) -> dict[str, str]:
        if self.headers is not None:
            return self.headers

        return {
            "Accept": "text/html, */*; q=0.01",
            "Accept-Encoding": "gzip, deflate, br, zstd",
            "Accept-Language": (
                "ko,en-US;q=0.9,en;q=0.8,ja;q=0.7,zh-CN;q=0.6,zh;q=0.5"
            ),
            "Connection": "keep-alive",
            "DNT": "1",
            "Host": "info.hansung.ac.kr",
            "Referer": self.referer_url,
            "Sec-Fetch-Dest": "empty",
            "Sec-Fetch-Mode": "cors",
            "Sec-Fetch-Site": "same-origin",
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/144.0.0.0 "
                "Safari/537.36"
            ),
            "X-Requested-With": "XMLHttpRequest",
            "sec-ch-ua": (
                '"Not(A:Brand";v="8", "Chromium";v="144", '
                '"Google Chrome";v="144"'
            ),
            "sec-ch-ua-mobile": "?0",
            "sec-ch-ua-platform": '"macOS"',
        }


class HansungAuthService(OrganizationAuthService):
    def __init__(self, *, config: HansungAuthConfig | None = None):
        self.config = config or HansungAuthConfig()

    async def authenticate(
        self,
        *,
        organization: Organization,
        login_id: str,
        password: str,
    ) -> OrganizationIdentity:
        if organization.auth_provider != OrganizationAuthProvider.HANSUNG_SIS:
            raise AuthIdentityProviderNotConfiguredException()

        payload = {
            "id": login_id,
            "passwd": password,
            "changePass": "",
            "return_url": "null",
        }

        try:
            async with httpx.AsyncClient(
                headers=self.config.resolved_headers(),
                follow_redirects=False,
                timeout=self.config.timeout_seconds,
            ) as client:
                await client.get(self.config.login_page_url)
                login_response = await client.post(
                    self.config.login_url,
                    data=payload,
                )
                self._ensure_login_succeeded(login_response=login_response)
                portal_response = await client.get(
                    login_response.headers["location"],
                    follow_redirects=True,
                )
                identity_response = await client.get(
                    self.config.responsive_index_url,
                    follow_redirects=True,
                )
        except httpx.TimeoutException as exc:
            raise AuthIdentityProviderUnavailableException(
                detail={
                    "organization_code": organization.code,
                    "reason": "timeout",
                }
            ) from exc
        except httpx.HTTPError as exc:
            raise AuthIdentityProviderUnavailableException(
                detail={
                    "organization_code": organization.code,
                    "reason": str(exc),
                }
            ) from exc

        self._ensure_portal_access(portal_response=portal_response)

        page_text = self._resolve_identity_text(
            identity_response, portal_response
        )
        name = self._extract_name(page_text)
        role = self._infer_role(
            page_text, login_id=login_id, has_name=name is not None
        )

        return OrganizationIdentity(
            login_id=login_id,
            role=role or self._fallback_role(login_id),
            name=name or login_id,
        )

    @staticmethod
    def _ensure_login_succeeded(*, login_response: httpx.Response) -> None:
        if login_response.status_code >= 500:
            raise AuthIdentityProviderUnavailableException()

        if login_response.status_code != LOGIN_REDIRECT_STATUS_CODE:
            raise AuthInvalidCredentialsException()

        location = login_response.headers.get("location")
        if location is None:
            raise AuthInvalidCredentialsException()

        if (
            urlparse(location).path
            != urlparse(HansungAuthConfig.portal_url).path
        ):
            raise AuthInvalidCredentialsException()

    @staticmethod
    def _ensure_portal_access(
        *,
        portal_response: httpx.Response,
    ) -> None:
        if portal_response.status_code >= 500:
            raise AuthIdentityProviderUnavailableException()

        if portal_response.status_code >= 400:
            raise AuthInvalidCredentialsException()

        if (
            urlparse(str(portal_response.url)).path
            != urlparse(HansungAuthConfig.portal_url).path
        ):
            raise AuthInvalidCredentialsException(
                detail={"reason": "unexpected_portal_redirect"}
            )

    @staticmethod
    def _resolve_identity_text(
        identity_response: httpx.Response,
        portal_response: httpx.Response,
    ) -> str:
        if (
            identity_response.status_code < 400
            and urlparse(str(identity_response.url)).path
            == urlparse(HansungAuthConfig.responsive_index_url).path
        ):
            return identity_response.text

        return portal_response.text

    @staticmethod
    def _infer_role(
        text: str,
        *,
        login_id: str,
        has_name: bool,
    ) -> UserRole | None:
        if any(
            marker in text
            for marker in (
                "/jsp_21/professor/",
                "/jsp_21/teacher/",
                "/jsp_21/staff/",
            )
        ):
            return UserRole.PROFESSOR

        if any(
            marker in text
            for marker in (
                "/jsp_21/student/",
                "hakbun=",
            )
        ):
            return UserRole.STUDENT

        if has_name:
            return HansungAuthService._fallback_role(login_id)

        return None

    @staticmethod
    def _fallback_role(login_id: str) -> UserRole:
        if login_id.isdigit() and len(login_id) >= 6:
            return UserRole.STUDENT

        return UserRole.PROFESSOR

    @staticmethod
    def _extract_name(text: str) -> str | None:
        compact_text = re.sub(r"\s+", " ", text)
        for pattern in NAME_PATTERNS:
            match = pattern.search(compact_text)
            if match is None:
                continue
            name = re.sub(r"<br\s*/?>", " ", match.group(1), flags=re.I)
            name = re.sub(r"<[^>]+>", " ", name)
            name = re.sub(r"\s+", " ", name).strip()
            if " " in name:
                name = name.split()[-1]
            if name:
                return name
        return None
