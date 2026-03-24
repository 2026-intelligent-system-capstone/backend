from uuid import UUID, uuid4

from jwt import PyJWTError

from app.auth.application.dto import AuthTokensDTO
from app.auth.application.exception import (
    AuthInvalidCredentialsException,
    AuthInvalidRefreshTokenException,
)
from app.auth.domain.command import (
    LoginCommand,
    LogoutCommand,
    RefreshTokenCommand,
)
from app.auth.domain.repository.auth_token import AuthTokenRepository
from app.auth.domain.usecase.auth import AuthUseCase
from app.user.domain.entity.user import UserStatus
from app.user.domain.repository.user import UserRepository
from core.config import config
from core.domain.types import TokenType
from core.helpers.argon2 import Argon2Helper
from core.helpers.token import TokenHelper


class AuthService(AuthUseCase):
    def __init__(
        self,
        *,
        user_repository: UserRepository,
        auth_token_repository: AuthTokenRepository,
    ):
        self.user_repository = user_repository
        self.auth_token_repository = auth_token_repository

    async def login(self, command: LoginCommand) -> AuthTokensDTO:
        user = await self.user_repository.get_by_email(command.email)
        if user is None or user.is_deleted or user.status == UserStatus.BLOCKED:
            raise AuthInvalidCredentialsException()

        if not Argon2Helper.verify(command.password, user.password):
            raise AuthInvalidCredentialsException()

        return await self._issue_tokens(user_id=user.id)

    async def refresh(self, command: RefreshTokenCommand) -> AuthTokensDTO:
        if command.refresh_token is None:
            raise AuthInvalidRefreshTokenException()

        payload = self._decode_refresh_token(command.refresh_token)
        user_id = self._parse_user_id(payload)
        jti = self._parse_jti(payload)

        stored_token = await self.auth_token_repository.get(
            user_id=user_id,
            jti=jti,
        )
        if stored_token != command.refresh_token:
            raise AuthInvalidRefreshTokenException()

        await self.auth_token_repository.delete(user_id=user_id, jti=jti)
        return await self._issue_tokens(user_id=user_id)

    async def logout(self, command: LogoutCommand) -> None:
        if command.refresh_token is None:
            return

        try:
            payload = self._decode_refresh_token(command.refresh_token)
            user_id = self._parse_user_id(payload)
            jti = self._parse_jti(payload)
        except AuthInvalidRefreshTokenException:
            return

        await self.auth_token_repository.delete(user_id=user_id, jti=jti)

    async def _issue_tokens(self, *, user_id: UUID) -> AuthTokensDTO:
        access_token = TokenHelper.create_token(
            payload={"sub": str(user_id)},
            token_type=TokenType.ACCESS,
        )
        refresh_jti = str(uuid4())
        refresh_token = TokenHelper.create_token(
            payload={"sub": str(user_id), "jti": refresh_jti},
            token_type=TokenType.REFRESH,
        )
        await self.auth_token_repository.save(
            user_id=user_id,
            jti=refresh_jti,
            refresh_token=refresh_token,
            expires_in=config.REFRESH_TOKEN_EXPIRE_MINUTES * 60,
        )
        return AuthTokensDTO(
            user_id=str(user_id),
            access_token=access_token,
            refresh_token=refresh_token,
        )

    @staticmethod
    def _parse_user_id(payload: dict[str, object]) -> UUID:
        try:
            user_id = payload["sub"]
            if not isinstance(user_id, str):
                raise ValueError
            return UUID(user_id)
        except (KeyError, ValueError) as exc:
            raise AuthInvalidRefreshTokenException() from exc

    @staticmethod
    def _parse_jti(payload: dict[str, object]) -> str:
        try:
            jti = payload["jti"]
            if not isinstance(jti, str):
                raise ValueError
            return jti
        except (KeyError, ValueError) as exc:
            raise AuthInvalidRefreshTokenException() from exc

    @staticmethod
    def _decode_refresh_token(token: str) -> dict[str, object]:
        try:
            payload = TokenHelper.decode_token(token)
        except (PyJWTError, KeyError, ValueError) as exc:
            raise AuthInvalidRefreshTokenException() from exc

        if payload.get("type") != TokenType.REFRESH.value:
            raise AuthInvalidRefreshTokenException()
        return payload
