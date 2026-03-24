import re
from html import unescape

import httpx

from app.auth.application.exception import (
    AuthIdentityProviderNotConfiguredException,
    AuthIdentityProviderUnavailableException,
    AuthInvalidCredentialsException,
)
from app.auth.domain.entity import AuthenticatedIdentity
from app.auth.domain.repository import IdentityVerifier
from app.organization.domain.entity import (
    Organization,
    OrganizationAuthProvider,
)
from app.user.domain.entity import UserRole
from core.config import config

LOGIN_HEADERS = {
    "Accept": "text/html, */*; q=0.01",
    "Accept-Encoding": "gzip, deflate, br, zstd",
    "Accept-Language": "ko,en-US;q=0.9,en;q=0.8,ja;q=0.7,zh-CN;q=0.6,zh;q=0.5",
    "Connection": "keep-alive",
    "DNT": "1",
    "Host": "info.hansung.ac.kr",
    "Referer": (
        "https://info.hansung.ac.kr/jsp/sugang/h_sugang_sincheong_main.jsp"
    ),
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
        '"Not(A:Brand";v="8", "Chromium";v="144", "Google Chrome";v="144"'
    ),
    "sec-ch-ua-mobile": "?0",
    "sec-ch-ua-platform": '"macOS"',
}

FAILURE_MARKERS = (
    "아이디 또는 비밀번호",
    "로그인 실패",
    "다시 로그인",
    "사용자 정보가 없습니다",
    "not authorized",
)

LOGIN_PAGE_MARKERS = (
    "changePass",
    "return_url",
    "gong_login",
    'name="password"',
    'type="password"',
)

NAME_PATTERNS = (
    re.compile(r"([가-힣]{2,10})\s*님"),
    re.compile(r"성명\s*[:：]?\s*([가-힣A-Za-z ]{2,40})"),
    re.compile(r"이름\s*[:：]?\s*([가-힣A-Za-z ]{2,40})"),
)


class HansungIdentityVerifier(IdentityVerifier):
    async def verify(
        self,
        *,
        organization: Organization,
        login_id: str,
        password: str,
    ) -> AuthenticatedIdentity:
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
                headers=LOGIN_HEADERS,
                follow_redirects=True,
                timeout=config.HANSUNG_REQUEST_TIMEOUT_SECONDS,
            ) as client:
                login_response = await client.post(
                    config.HANSUNG_LOGIN_URL,
                    data=payload,
                )
                info_response = await client.get(config.HANSUNG_INFO_URL)
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

        self._ensure_authenticated(
            login_id=login_id,
            login_response=login_response,
            info_response=info_response,
        )

        page_text = self._merge_text(login_response.text, info_response.text)
        return AuthenticatedIdentity(
            login_id=login_id,
            role=self._infer_role(page_text, login_id),
            name=self._extract_name(page_text, login_id),
        )

    @staticmethod
    def _ensure_authenticated(
        *,
        login_id: str,
        login_response: httpx.Response,
        info_response: httpx.Response,
    ) -> None:
        if (
            login_response.status_code >= 500
            or info_response.status_code >= 500
        ):
            raise AuthIdentityProviderUnavailableException()

        if (
            login_response.status_code >= 400
            or info_response.status_code >= 400
        ):
            raise AuthInvalidCredentialsException()

        merged_text = HansungIdentityVerifier._merge_text(
            login_response.text,
            info_response.text,
        )
        lowered_text = merged_text.lower()

        if any(marker in lowered_text for marker in FAILURE_MARKERS):
            raise AuthInvalidCredentialsException()

        if HansungIdentityVerifier._looks_like_login_page(lowered_text):
            raise AuthInvalidCredentialsException(
                detail={"login_id": login_id, "reason": "login_page_returned"}
            )

    @staticmethod
    def _looks_like_login_page(text: str) -> bool:
        matched_markers = [
            marker for marker in LOGIN_PAGE_MARKERS if marker in text
        ]
        return len(matched_markers) >= 2

    @staticmethod
    def _merge_text(*parts: str) -> str:
        return " ".join(unescape(part or "") for part in parts)

    @staticmethod
    def _infer_role(text: str, login_id: str) -> UserRole:
        if any(keyword in text for keyword in ("교수", "교원", "교직원")):
            return UserRole.PROFESSOR

        if "학생" in text:
            return UserRole.STUDENT

        if login_id.isdigit() and len(login_id) >= 8:
            return UserRole.STUDENT

        return UserRole.PROFESSOR

    @staticmethod
    def _extract_name(text: str, fallback: str) -> str:
        compact_text = re.sub(r"\s+", " ", text)
        for pattern in NAME_PATTERNS:
            match = pattern.search(compact_text)
            if match is None:
                continue
            name = match.group(1).strip()
            if name:
                return name
        return fallback
