from dataclasses import dataclass
from uuid import UUID, uuid4

from jwt import PyJWTError

from app.auth.domain.exception import AuthInvalidRefreshTokenDomainException
from app.user.domain.entity import User
from core.domain.types import TokenType
from core.helpers.token import TokenHelper


@dataclass(frozen=True)
class AuthTokens:
    user_id: str
    organization_id: str
    organization_code: str
    role: str
    access_token: str
    refresh_token: str

    @classmethod
    def issue(
        cls,
        *,
        user_id: UUID,
        organization_id: UUID,
        organization_code: str,
        role: str,
    ) -> tuple["AuthTokens", str]:
        access_token = TokenHelper.create_token(
            payload={"sub": str(user_id)},
            token_type=TokenType.ACCESS,
        )
        refresh_jti = str(uuid4())
        refresh_token = TokenHelper.create_token(
            payload={"sub": str(user_id), "jti": refresh_jti},
            token_type=TokenType.REFRESH,
        )
        return (
            cls(
                user_id=str(user_id),
                organization_id=str(organization_id),
                organization_code=organization_code,
                role=role,
                access_token=access_token,
                refresh_token=refresh_token,
            ),
            refresh_jti,
        )

    @classmethod
    def issue_for_user(
        cls,
        *,
        user: User,
        organization_code: str,
    ) -> tuple["AuthTokens", str]:
        return cls.issue(
            user_id=user.id,
            organization_id=user.organization_id,
            organization_code=organization_code,
            role=user.role.value,
        )

    @staticmethod
    def decode_refresh_token(token: str) -> dict[str, object]:
        try:
            payload = TokenHelper.decode_token(token)
        except (PyJWTError, KeyError, ValueError) as exc:
            raise AuthInvalidRefreshTokenDomainException() from exc

        if payload.get("type") != TokenType.REFRESH.value:
            raise AuthInvalidRefreshTokenDomainException()
        return payload

    @classmethod
    def parse_refresh_token(cls, token: str) -> tuple[UUID, str]:
        payload = cls.decode_refresh_token(token)
        try:
            user_id = payload["sub"]
            jti = payload["jti"]
            if not isinstance(user_id, str) or not isinstance(jti, str):
                raise ValueError
            return UUID(user_id), jti
        except (KeyError, ValueError) as exc:
            raise AuthInvalidRefreshTokenDomainException() from exc
