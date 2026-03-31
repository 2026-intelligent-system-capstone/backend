from uuid import UUID

import pytest

from app.auth.application.exception import (
    AuthIdentityProviderNotConfiguredException,
    AuthIdentityProviderUnavailableException,
    AuthInvalidCredentialsException,
    AuthInvalidRefreshTokenException,
)
from app.auth.application.service import AuthService
from app.auth.domain.command import (
    LoginCommand,
    LogoutCommand,
    RefreshTokenCommand,
)
from app.auth.domain.repository import AuthTokenRepository
from app.organization.domain.entity import (
    Organization,
    OrganizationAuthProvider,
    OrganizationIdentity,
)
from app.organization.domain.repository import OrganizationRepository
from app.organization.domain.service import OrganizationAuthService
from app.user.domain.entity import User, UserRole, UserStatus
from app.user.domain.repository import UserRepository
from core.domain.types import TokenType
from core.helpers.token import TokenHelper

ORGANIZATION_ID = UUID("11111111-1111-1111-1111-111111111111")
TEST_PROFESSOR_LOGIN_ID = "90000001"
TEST_STUDENT_LOGIN_ID = "90000002"


class InMemoryOrganizationRepository(OrganizationRepository):
    def __init__(self, organizations: list[Organization] | None = None):
        self.organizations = {org.id: org for org in organizations or []}

    async def save(self, entity: Organization) -> None:
        self.organizations[entity.id] = entity

    async def get_by_id(self, entity_id: UUID) -> Organization | None:
        return self.organizations.get(entity_id)

    async def list(self) -> list[Organization]:
        return list(self.organizations.values())

    async def get_by_code(self, code: str) -> Organization | None:
        return next(
            (org for org in self.organizations.values() if org.code == code),
            None,
        )


class InMemoryUserRepository(UserRepository):
    def __init__(self, users: list[User] | None = None):
        self.users = {user.id: user for user in users or []}

    async def save(self, entity: User) -> None:
        self.users[entity.id] = entity

    async def list_by_organization(
        self,
        organization_id: UUID,
    ) -> list[User]:
        return [
            user
            for user in self.users.values()
            if user.organization_id == organization_id
        ]

    async def get_by_id(self, entity_id: UUID) -> User | None:
        return next(
            (
                user
                for user in self.users.values()
                if str(user.id) == str(entity_id)
            ),
            None,
        )

    async def list(self) -> list[User]:
        return list(self.users.values())

    async def get_by_organization_and_login_id(
        self,
        organization_id: UUID,
        login_id: str,
    ) -> User | None:
        return next(
            (
                user
                for user in self.users.values()
                if user.organization_id == organization_id
                and user.login_id == login_id
            ),
            None,
        )


class InMemoryAuthTokenRepository(AuthTokenRepository):
    def __init__(self):
        self.tokens: dict[str, str] = {}

    async def save(
        self,
        *,
        user_id: UUID,
        jti: str,
        refresh_token: str,
        expires_in: int,
    ) -> None:
        del expires_in
        self.tokens[f"auth:user:{user_id}:refresh:{jti}"] = refresh_token

    async def get(self, *, user_id: UUID, jti: str) -> str | None:
        return self.tokens.get(f"auth:user:{user_id}:refresh:{jti}")

    async def delete(self, *, user_id: UUID, jti: str) -> None:
        self.tokens.pop(f"auth:user:{user_id}:refresh:{jti}", None)


class FakeOrganizationAuthService(OrganizationAuthService):
    def __init__(self, identity: OrganizationIdentity | None = None):
        self.identity = identity or OrganizationIdentity(
            login_id="20260001",
            role=UserRole.STUDENT,
            name="김테스트",
            email="student@example.com",
        )
        self.called = False

    async def authenticate(
        self,
        *,
        organization: Organization,
        login_id: str,
        password: str,
    ) -> OrganizationIdentity:
        del organization
        del password
        self.called = True
        return OrganizationIdentity(
            login_id=login_id,
            role=self.identity.role,
            name=self.identity.name,
            email=self.identity.email,
        )


def make_organization() -> Organization:
    organization = Organization(
        code="univ_hansung",
        name="한성대학교",
        auth_provider=OrganizationAuthProvider.HANSUNG_SIS,
    )
    organization.id = ORGANIZATION_ID
    return organization


def make_user(login_id: str = "20260001") -> User:
    return User(
        organization_id=ORGANIZATION_ID,
        login_id=login_id,
        role=UserRole.STUDENT,
        email="student@example.com",
        name="김테스트",
    )


@pytest.mark.asyncio
async def test_login_success_creates_user_and_stores_tokens():
    user_repository = InMemoryUserRepository()
    auth_token_repository = InMemoryAuthTokenRepository()
    service = AuthService(
        organization_repository=InMemoryOrganizationRepository([
            make_organization()
        ]),
        user_repository=user_repository,
        auth_token_repository=auth_token_repository,
        organization_auth_service=FakeOrganizationAuthService(),
    )

    tokens = await service.login(
        LoginCommand(
            organization_code="univ_hansung",
            login_id="20260001",
            password="secure_password123",
        )
    )

    refresh_payload = TokenHelper.decode_token(tokens.refresh_token)
    stored_token = await auth_token_repository.get(
        user_id=UUID(tokens.user_id),
        jti=refresh_payload["jti"],
    )
    saved_user = await user_repository.get_by_organization_and_login_id(
        ORGANIZATION_ID,
        "20260001",
    )

    assert saved_user is not None
    assert tokens.organization_code == "univ_hansung"
    assert tokens.role == "student"
    assert stored_token == tokens.refresh_token


@pytest.mark.asyncio
async def test_login_updates_existing_user_role():
    existing_user = make_user()
    service = AuthService(
        organization_repository=InMemoryOrganizationRepository([
            make_organization()
        ]),
        user_repository=InMemoryUserRepository([existing_user]),
        auth_token_repository=InMemoryAuthTokenRepository(),
        organization_auth_service=FakeOrganizationAuthService(
            OrganizationIdentity(
                login_id="20260001",
                role=UserRole.PROFESSOR,
                name="김교수",
                email="professor@example.com",
            )
        ),
    )

    tokens = await service.login(
        LoginCommand(
            organization_code="univ_hansung",
            login_id="20260001",
            password="secure_password123",
        )
    )

    assert tokens.role == "professor"


@pytest.mark.asyncio
async def test_login_bypasses_provider_for_test_professor_id():
    existing_user = make_user(login_id=TEST_PROFESSOR_LOGIN_ID)
    existing_user.role = UserRole.PROFESSOR
    fake_auth_service = FakeOrganizationAuthService()
    service = AuthService(
        organization_repository=InMemoryOrganizationRepository([
            make_organization()
        ]),
        user_repository=InMemoryUserRepository([existing_user]),
        auth_token_repository=InMemoryAuthTokenRepository(),
        organization_auth_service=fake_auth_service,
    )

    tokens = await service.login(
        LoginCommand(
            organization_code="univ_hansung",
            login_id=TEST_PROFESSOR_LOGIN_ID,
            password="whatever123",
        )
    )

    assert tokens.role == "professor"
    assert fake_auth_service.called is False


@pytest.mark.asyncio
async def test_login_bypasses_provider_for_test_student_id():
    existing_user = make_user(login_id=TEST_STUDENT_LOGIN_ID)
    fake_auth_service = FakeOrganizationAuthService()
    service = AuthService(
        organization_repository=InMemoryOrganizationRepository([
            make_organization()
        ]),
        user_repository=InMemoryUserRepository([existing_user]),
        auth_token_repository=InMemoryAuthTokenRepository(),
        organization_auth_service=fake_auth_service,
    )

    tokens = await service.login(
        LoginCommand(
            organization_code="univ_hansung",
            login_id=TEST_STUDENT_LOGIN_ID,
            password="whatever123",
        )
    )

    assert tokens.role == "student"
    assert fake_auth_service.called is False


@pytest.mark.asyncio
async def test_login_invalid_organization_raises():
    service = AuthService(
        organization_repository=InMemoryOrganizationRepository(),
        user_repository=InMemoryUserRepository(),
        auth_token_repository=InMemoryAuthTokenRepository(),
        organization_auth_service=FakeOrganizationAuthService(),
    )

    with pytest.raises(AuthInvalidCredentialsException):
        await service.login(
            LoginCommand(
                organization_code="missing",
                login_id="20260001",
                password="secure_password123",
            )
        )


@pytest.mark.asyncio
async def test_login_invalid_credentials_does_not_create_user():
    class FailingService(OrganizationAuthService):
        async def authenticate(self, **kwargs):
            del kwargs
            raise AuthInvalidCredentialsException()

    user_repository = InMemoryUserRepository()
    service = AuthService(
        organization_repository=InMemoryOrganizationRepository([
            make_organization()
        ]),
        user_repository=user_repository,
        auth_token_repository=InMemoryAuthTokenRepository(),
        organization_auth_service=FailingService(),
    )

    with pytest.raises(AuthInvalidCredentialsException):
        await service.login(
            LoginCommand(
                organization_code="univ_hansung",
                login_id="20260001",
                password="wrong-password",
            )
        )

    assert user_repository.users == {}


@pytest.mark.asyncio
async def test_login_converts_provider_error_to_invalid_credentials():
    class FailingService(OrganizationAuthService):
        async def authenticate(self, **kwargs):
            del kwargs
            raise RuntimeError("unexpected provider error")

    service = AuthService(
        organization_repository=InMemoryOrganizationRepository([
            make_organization()
        ]),
        user_repository=InMemoryUserRepository(),
        auth_token_repository=InMemoryAuthTokenRepository(),
        organization_auth_service=FailingService(),
    )

    with pytest.raises(AuthInvalidCredentialsException):
        await service.login(
            LoginCommand(
                organization_code="univ_hansung",
                login_id="20260001",
                password="secure_password123",
            )
        )


@pytest.mark.asyncio
async def test_login_rejects_deleted_existing_user():
    existing_user = make_user()
    existing_user.is_deleted = True
    service = AuthService(
        organization_repository=InMemoryOrganizationRepository([
            make_organization()
        ]),
        user_repository=InMemoryUserRepository([existing_user]),
        auth_token_repository=InMemoryAuthTokenRepository(),
        organization_auth_service=FakeOrganizationAuthService(),
    )

    with pytest.raises(AuthInvalidCredentialsException):
        await service.login(
            LoginCommand(
                organization_code="univ_hansung",
                login_id="20260001",
                password="secure_password123",
            )
        )


@pytest.mark.asyncio
async def test_login_rejects_blocked_existing_user():
    existing_user = make_user()
    existing_user.status = UserStatus.BLOCKED
    service = AuthService(
        organization_repository=InMemoryOrganizationRepository([
            make_organization()
        ]),
        user_repository=InMemoryUserRepository([existing_user]),
        auth_token_repository=InMemoryAuthTokenRepository(),
        organization_auth_service=FakeOrganizationAuthService(),
    )

    with pytest.raises(AuthInvalidCredentialsException):
        await service.login(
            LoginCommand(
                organization_code="univ_hansung",
                login_id="20260001",
                password="secure_password123",
            )
        )


@pytest.mark.asyncio
async def test_login_identity_provider_not_configured_bubbles_up():
    class FailingService(OrganizationAuthService):
        async def authenticate(self, **kwargs):
            del kwargs
            raise AuthIdentityProviderNotConfiguredException()

    service = AuthService(
        organization_repository=InMemoryOrganizationRepository([
            make_organization()
        ]),
        user_repository=InMemoryUserRepository(),
        auth_token_repository=InMemoryAuthTokenRepository(),
        organization_auth_service=FailingService(),
    )

    with pytest.raises(AuthIdentityProviderNotConfiguredException):
        await service.login(
            LoginCommand(
                organization_code="univ_hansung",
                login_id="20260001",
                password="secure_password123",
            )
        )


@pytest.mark.asyncio
async def test_login_identity_provider_unavailable_bubbles_up():
    class FailingService(OrganizationAuthService):
        async def authenticate(self, **kwargs):
            del kwargs
            raise AuthIdentityProviderUnavailableException()

    service = AuthService(
        organization_repository=InMemoryOrganizationRepository([
            make_organization()
        ]),
        user_repository=InMemoryUserRepository(),
        auth_token_repository=InMemoryAuthTokenRepository(),
        organization_auth_service=FailingService(),
    )

    with pytest.raises(AuthIdentityProviderUnavailableException):
        await service.login(
            LoginCommand(
                organization_code="univ_hansung",
                login_id="20260001",
                password="secure_password123",
            )
        )


@pytest.mark.asyncio
async def test_refresh_rotates_refresh_token():
    user = make_user()
    auth_token_repository = InMemoryAuthTokenRepository()
    service = AuthService(
        organization_repository=InMemoryOrganizationRepository([
            make_organization()
        ]),
        user_repository=InMemoryUserRepository([user]),
        auth_token_repository=auth_token_repository,
        organization_auth_service=FakeOrganizationAuthService(),
    )

    first_tokens = await service.login(
        LoginCommand(
            organization_code="univ_hansung",
            login_id="20260001",
            password="secure_password123",
        )
    )
    first_payload = TokenHelper.decode_token(first_tokens.refresh_token)

    refreshed_tokens = await service.refresh(
        RefreshTokenCommand(refresh_token=first_tokens.refresh_token)
    )
    refreshed_payload = TokenHelper.decode_token(refreshed_tokens.refresh_token)

    assert refreshed_tokens.refresh_token != first_tokens.refresh_token
    assert (
        await auth_token_repository.get(
            user_id=UUID(first_tokens.user_id),
            jti=first_payload["jti"],
        )
        is None
    )
    assert (
        await auth_token_repository.get(
            user_id=UUID(refreshed_tokens.user_id),
            jti=refreshed_payload["jti"],
        )
        == refreshed_tokens.refresh_token
    )


@pytest.mark.asyncio
async def test_refresh_with_unknown_token_raises():
    service = AuthService(
        organization_repository=InMemoryOrganizationRepository([
            make_organization()
        ]),
        user_repository=InMemoryUserRepository(),
        auth_token_repository=InMemoryAuthTokenRepository(),
        organization_auth_service=FakeOrganizationAuthService(),
    )

    invalid_refresh = TokenHelper.create_token(
        payload={"sub": str(UUID(int=1)), "jti": "missing-token"},
        token_type=TokenType.REFRESH,
    )

    with pytest.raises(AuthInvalidRefreshTokenException):
        await service.refresh(
            RefreshTokenCommand(refresh_token=invalid_refresh)
        )


@pytest.mark.asyncio
async def test_refresh_with_access_token_raises():
    service = AuthService(
        organization_repository=InMemoryOrganizationRepository([
            make_organization()
        ]),
        user_repository=InMemoryUserRepository(),
        auth_token_repository=InMemoryAuthTokenRepository(),
        organization_auth_service=FakeOrganizationAuthService(),
    )
    access_token = TokenHelper.create_token(
        payload={"sub": str(UUID(int=1))},
        token_type=TokenType.ACCESS,
    )

    with pytest.raises(AuthInvalidRefreshTokenException):
        await service.refresh(RefreshTokenCommand(refresh_token=access_token))


@pytest.mark.asyncio
async def test_refresh_raises_when_organization_is_missing():
    user = make_user()
    auth_token_repository = InMemoryAuthTokenRepository()
    service = AuthService(
        organization_repository=InMemoryOrganizationRepository(),
        user_repository=InMemoryUserRepository([user]),
        auth_token_repository=auth_token_repository,
        organization_auth_service=FakeOrganizationAuthService(),
    )
    refresh_token = TokenHelper.create_token(
        payload={"sub": str(user.id), "jti": "refresh-jti"},
        token_type=TokenType.REFRESH,
    )
    await auth_token_repository.save(
        user_id=user.id,
        jti="refresh-jti",
        refresh_token=refresh_token,
        expires_in=3600,
    )

    with pytest.raises(AuthInvalidRefreshTokenException):
        await service.refresh(RefreshTokenCommand(refresh_token=refresh_token))


@pytest.mark.asyncio
async def test_logout_deletes_refresh_token():
    auth_token_repository = InMemoryAuthTokenRepository()
    service = AuthService(
        organization_repository=InMemoryOrganizationRepository([
            make_organization()
        ]),
        user_repository=InMemoryUserRepository(),
        auth_token_repository=auth_token_repository,
        organization_auth_service=FakeOrganizationAuthService(),
    )

    tokens = await service.login(
        LoginCommand(
            organization_code="univ_hansung",
            login_id="20260001",
            password="secure_password123",
        )
    )
    refresh_payload = TokenHelper.decode_token(tokens.refresh_token)

    await service.logout(LogoutCommand(refresh_token=tokens.refresh_token))

    assert (
        await auth_token_repository.get(
            user_id=UUID(tokens.user_id),
            jti=refresh_payload["jti"],
        )
        is None
    )


@pytest.mark.asyncio
async def test_logout_ignores_malformed_refresh_token():
    auth_token_repository = InMemoryAuthTokenRepository()
    service = AuthService(
        organization_repository=InMemoryOrganizationRepository([
            make_organization()
        ]),
        user_repository=InMemoryUserRepository(),
        auth_token_repository=auth_token_repository,
        organization_auth_service=FakeOrganizationAuthService(),
    )

    await service.logout(LogoutCommand(refresh_token="not-a-jwt"))

    assert auth_token_repository.tokens == {}
