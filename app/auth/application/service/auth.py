from uuid import UUID, uuid4

from jwt import PyJWTError

from app.auth.application.dto import AuthTokensDTO
from app.auth.application.exception import (
    AuthIdentityProviderNotConfiguredException,
    AuthIdentityProviderUnavailableException,
    AuthInvalidCredentialsException,
    AuthInvalidRefreshTokenException,
)
from app.auth.domain.command import (
    LoginCommand,
    LogoutCommand,
    RefreshTokenCommand,
)
from app.auth.domain.repository import AuthTokenRepository, IdentityVerifier
from app.auth.domain.usecase.auth import AuthUseCase
from app.organization.domain.repository import OrganizationRepository
from app.user.domain.entity import Profile, User, UserRole, UserStatus
from app.user.domain.repository import UserRepository
from core.config import config
from core.domain.types import TokenType
from core.helpers.token import TokenHelper


class AuthService(AuthUseCase):
    def __init__(
        self,
        *,
        organization_repository: OrganizationRepository,
        user_repository: UserRepository,
        auth_token_repository: AuthTokenRepository,
        identity_verifier: IdentityVerifier,
    ):
        self.organization_repository = organization_repository
        self.user_repository = user_repository
        self.auth_token_repository = auth_token_repository
        self.identity_verifier = identity_verifier

    async def login(self, command: LoginCommand) -> AuthTokensDTO:
        organization = await self.organization_repository.get_by_code(
            command.organization_code
        )
        if organization is None or not organization.is_active:
            raise AuthInvalidCredentialsException()

        try:
            identity = await self.identity_verifier.verify(
                organization=organization,
                login_id=command.login_id,
                password=command.password,
            )
        except (
            AuthIdentityProviderNotConfiguredException,
            AuthIdentityProviderUnavailableException,
        ):
            raise
        except Exception as exc:
            raise AuthInvalidCredentialsException() from exc

        user = await self.user_repository.get_by_organization_and_login_id(
            organization.id,
            identity.login_id,
        )

        if user is None:
            user = User(
                organization_id=organization.id,
                login_id=identity.login_id,
                role=identity.role,
                email=identity.email,
                profile=Profile(
                    nickname=identity.name,
                    name=identity.name,
                ),
            )
        else:
            if user.is_deleted or user.status == UserStatus.BLOCKED:
                raise AuthInvalidCredentialsException()

            user.role = identity.role
            user.email = identity.email
            user.profile = Profile(
                nickname=user.profile.nickname,
                name=identity.name,
                phone_number=user.profile.phone_number,
                profile_image_id=user.profile.profile_image_id,
            )

        saved_user = await self.user_repository.save(user)

        return await self._issue_tokens(
            user_id=saved_user.id,
            organization_id=organization.id,
            organization_code=organization.code,
            role=saved_user.role,
        )

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

        user = await self.user_repository.get_by_id(user_id)
        if user is None or user.is_deleted:
            raise AuthInvalidRefreshTokenException()

        organization = await self.organization_repository.get_by_id(
            user.organization_id
        )
        if organization is None:
            raise AuthInvalidRefreshTokenException()

        await self.auth_token_repository.delete(user_id=user_id, jti=jti)
        return await self._issue_tokens(
            user_id=user_id,
            organization_id=organization.id,
            organization_code=organization.code,
            role=user.role,
        )

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

    async def _issue_tokens(
        self,
        *,
        user_id: UUID,
        organization_id: UUID,
        organization_code: str,
        role: UserRole,
    ) -> AuthTokensDTO:
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
            organization_id=str(organization_id),
            organization_code=organization_code,
            role=role.value,
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
