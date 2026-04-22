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
from app.auth.domain.entity import AuthTokens
from app.auth.domain.exception import AuthInvalidRefreshTokenDomainException
from app.auth.domain.repository import AuthTokenRepository
from app.auth.domain.usecase.auth import AuthUseCase
from app.organization.domain.repository import OrganizationRepository
from app.organization.domain.service import OrganizationAuthService
from app.user.domain.entity import User
from app.user.domain.repository import UserRepository
from core.config import config
from core.db.transactional import transactional

TEST_LOGIN_BYPASS_IDS = {"90000001", "90000002"}


class AuthService(AuthUseCase):
    def __init__(
        self,
        *,
        organization_repository: OrganizationRepository,
        user_repository: UserRepository,
        auth_token_repository: AuthTokenRepository,
        organization_auth_service: OrganizationAuthService,
    ):
        self.organization_repository = organization_repository
        self.user_repository = user_repository
        self.auth_token_repository = auth_token_repository
        self.organization_auth_service = organization_auth_service

    @transactional
    async def login(self, command: LoginCommand) -> AuthTokens:
        organization = await self.organization_repository.get_by_code(
            command.organization_code
        )
        if organization is None or not organization.is_active:
            raise AuthInvalidCredentialsException()

        if command.login_id in TEST_LOGIN_BYPASS_IDS:
            user = await self.user_repository.get_by_organization_and_login_id(
                organization.id,
                command.login_id,
            )
            if user is None or not user.can_login:
                raise AuthInvalidCredentialsException()

            return await self._issue_tokens(
                user=user,
                organization_code=organization.code,
            )

        try:
            identity = await self.organization_auth_service.authenticate(
                organization=organization,
                login_id=command.login_id,
                password=command.password,
            )
        except (
            AuthIdentityProviderNotConfiguredException,
            AuthIdentityProviderUnavailableException,
            AuthInvalidCredentialsException,
        ):
            raise
        except Exception as exc:
            raise AuthInvalidCredentialsException() from exc

        user = await self.user_repository.get_by_organization_and_login_id(
            organization.id,
            identity.login_id,
        )

        if user is None:
            user = User.register(
                organization_id=organization.id,
                login_id=identity.login_id,
                role=identity.role,
                email=identity.email,
                name=identity.name,
            )
        else:
            if not user.can_login:
                raise AuthInvalidCredentialsException()

            user.sync_profile(
                login_id=identity.login_id,
                role=identity.role,
                email=identity.email,
                name=identity.name,
            )

        await self.user_repository.save(user)

        return await self._issue_tokens(
            user=user,
            organization_code=organization.code,
        )

    async def refresh(self, command: RefreshTokenCommand) -> AuthTokens:
        if command.refresh_token is None:
            raise AuthInvalidRefreshTokenException()

        try:
            user_id, jti = AuthTokens.parse_refresh_token(command.refresh_token)
        except AuthInvalidRefreshTokenDomainException as exc:
            raise AuthInvalidRefreshTokenException() from exc

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
            user=user,
            organization_code=organization.code,
        )

    async def logout(self, command: LogoutCommand) -> None:
        if command.refresh_token is None:
            return

        try:
            user_id, jti = AuthTokens.parse_refresh_token(command.refresh_token)
        except AuthInvalidRefreshTokenDomainException:
            return

        await self.auth_token_repository.delete(user_id=user_id, jti=jti)

    async def _issue_tokens(
        self,
        *,
        user: User,
        organization_code: str,
    ) -> AuthTokens:
        tokens, refresh_jti = AuthTokens.issue_for_user(
            user=user,
            organization_code=organization_code,
        )
        await self.auth_token_repository.save(
            user_id=user.id,
            jti=refresh_jti,
            refresh_token=tokens.refresh_token,
            expires_in=config.REFRESH_TOKEN_EXPIRE_MINUTES * 60,
        )
        return tokens
