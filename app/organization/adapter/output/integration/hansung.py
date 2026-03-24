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

LOGIN_SUCCESS_STATUS_CODE = 302

CLIENT_REDIRECT_MARKERS = (
    "parent.location='/'",
    'parent.location="/"',
    "top.location='/'",
    'top.location="/"',
)

NAME_PATTERNS = (
    re.compile(r"([가-힣]{2,10})\s*님"),
    re.compile(r"성명\s*[:：]?\s*([가-힣A-Za-z ]{2,40})"),
    re.compile(r"이름\s*[:：]?\s*([가-힣A-Za-z ]{2,40})"),
)


@dataclass(frozen=True)
class HansungAuthConfig:
    login_url: str = "https://info.hansung.ac.kr/servlet/s_gong.gong_login_ssl"
    info_url: str = (
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
            "Referer": self.info_url,
            "Sec-Fetch-Dest": "empty",
            "Sec-Fetch-Mode": "cors",
            "Sec-Fetch-Site": "same-origin",
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/144.0.0.0 Safari/537.36"
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
            "password": password,
            "changePass": "",
            "return_url": "null",
        }

        try:
            async with httpx.AsyncClient(
                headers=self.config.resolved_headers(),
                follow_redirects=False,
                timeout=self.config.timeout_seconds,
            ) as client:
                login_response = await client.post(
                    self.config.login_url,
                    data=payload,
                )
                info_response = await client.get(self.config.info_url)
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

        self._ensure_login_succeeded(login_response=login_response)
        self._ensure_session_is_authenticated(info_response=info_response)

        page_text = info_response.text
        name = self._extract_name(page_text)
        role = self._infer_role(
            page_text, login_id=login_id, has_name=name is not None
        )

        if name is None and role is None:
            raise AuthInvalidCredentialsException(
                detail={
                    "organization_code": organization.code,
                    "reason": "authenticated_identity_not_detected",
                }
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

        if login_response.status_code != LOGIN_SUCCESS_STATUS_CODE:
            raise AuthInvalidCredentialsException()

        location = login_response.headers.get("location")
        if location is None:
            raise AuthInvalidCredentialsException()

        if urlparse(location).path != urlparse(HansungAuthConfig.info_url).path:
            raise AuthInvalidCredentialsException()

    @staticmethod
    def _ensure_session_is_authenticated(
        *,
        info_response: httpx.Response,
    ) -> None:
        if info_response.status_code >= 500:
            raise AuthIdentityProviderUnavailableException()

        if info_response.status_code >= 400:
            raise AuthInvalidCredentialsException()

        lowered_text = info_response.text.lower()
        if any(marker in lowered_text for marker in CLIENT_REDIRECT_MARKERS):
            raise AuthInvalidCredentialsException(
                detail={"reason": "unauthenticated_session"}
            )

    @staticmethod
    def _infer_role(
        text: str,
        *,
        login_id: str,
        has_name: bool,
    ) -> UserRole | None:
        if any(keyword in text for keyword in ("교수", "교원", "교직원")):
            return UserRole.PROFESSOR

        if "학생" in text:
            return UserRole.STUDENT

        if has_name:
            return HansungAuthService._fallback_role(login_id)

        return None

    @staticmethod
    def _fallback_role(login_id: str) -> UserRole:
        if login_id.isdigit() and len(login_id) >= 8:
            return UserRole.STUDENT

        return UserRole.PROFESSOR

    @staticmethod
    def _extract_name(text: str) -> str | None:
        compact_text = re.sub(r"\s+", " ", text)
        for pattern in NAME_PATTERNS:
            match = pattern.search(compact_text)
            if match is None:
                continue
            name = match.group(1).strip()
            if name:
                return name
        return None
