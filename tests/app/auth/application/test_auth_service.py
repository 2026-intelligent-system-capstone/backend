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
from app.auth.domain.entity import AuthenticatedIdentity
from app.auth.domain.repository import AuthTokenRepository, IdentityVerifier
from app.organization.domain.entity import (
    Organization,
    OrganizationAuthProvider,
)
from app.organization.domain.repository import OrganizationRepository
from app.user.domain.entity import Profile, User, UserRole
from app.user.domain.repository import UserRepository
from core.domain.types import TokenType
from core.helpers.token import TokenHelper

ORGANIZATION_ID = UUID("11111111-1111-1111-1111-111111111111")


class InMemoryOrganizationRepository(OrganizationRepository):
    def __init__(self, organizations: list[Organization] | None = None):
        self.organizations = {org.id: org for org in organizations or []}

    async def save(self, entity: Organization) -> Organization:
        self.organizations[entity.id] = entity
        return entity

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

    async def save(self, entity: User) -> User:
        self.users[entity.id] = entity
        return entity

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


class FakeIdentityVerifier(IdentityVerifier):
    def __init__(self, identity: AuthenticatedIdentity | None = None):
        self.identity = identity or AuthenticatedIdentity(
            login_id="20260001",
            role=UserRole.STUDENT,
            name="김테스트",
            email="student@example.com",
        )

    async def verify(
        self,
        *,
        organization: Organization,
        login_id: str,
        password: str,
    ) -> AuthenticatedIdentity:
        del organization
        del password
        return AuthenticatedIdentity(
            login_id=login_id,
            role=self.identity.role,
            name=self.identity.name,
            email=self.identity.email,
        )


def make_organization() -> Organization:
    organization = Organization(
        code="hansung",
        name="Hansung University",
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
        profile=Profile(nickname="tester", name="김테스트"),
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
        identity_verifier=FakeIdentityVerifier(),
    )

    tokens = await service.login(
        LoginCommand(
            organization_code="hansung",
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
    assert tokens.organization_code == "hansung"
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
        identity_verifier=FakeIdentityVerifier(
            AuthenticatedIdentity(
                login_id="20260001",
                role=UserRole.PROFESSOR,
                name="김교수",
                email="professor@example.com",
            )
        ),
    )

    tokens = await service.login(
        LoginCommand(
            organization_code="hansung",
            login_id="20260001",
            password="secure_password123",
        )
    )

    assert tokens.role == "professor"


@pytest.mark.asyncio
async def test_login_invalid_organization_raises():
    service = AuthService(
        organization_repository=InMemoryOrganizationRepository(),
        user_repository=InMemoryUserRepository(),
        auth_token_repository=InMemoryAuthTokenRepository(),
        identity_verifier=FakeIdentityVerifier(),
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
async def test_login_identity_provider_not_configured_bubbles_up():
    class FailingVerifier(IdentityVerifier):
        async def verify(self, **kwargs):
            del kwargs
            raise AuthIdentityProviderNotConfiguredException()

    service = AuthService(
        organization_repository=InMemoryOrganizationRepository([
            make_organization()
        ]),
        user_repository=InMemoryUserRepository(),
        auth_token_repository=InMemoryAuthTokenRepository(),
        identity_verifier=FailingVerifier(),
    )

    with pytest.raises(AuthIdentityProviderNotConfiguredException):
        await service.login(
            LoginCommand(
                organization_code="hansung",
                login_id="20260001",
                password="secure_password123",
            )
        )


@pytest.mark.asyncio
async def test_login_identity_provider_unavailable_bubbles_up():
    class FailingVerifier(IdentityVerifier):
        async def verify(self, **kwargs):
            del kwargs
            raise AuthIdentityProviderUnavailableException()

    service = AuthService(
        organization_repository=InMemoryOrganizationRepository([
            make_organization()
        ]),
        user_repository=InMemoryUserRepository(),
        auth_token_repository=InMemoryAuthTokenRepository(),
        identity_verifier=FailingVerifier(),
    )

    with pytest.raises(AuthIdentityProviderUnavailableException):
        await service.login(
            LoginCommand(
                organization_code="hansung",
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
        identity_verifier=FakeIdentityVerifier(),
    )

    first_tokens = await service.login(
        LoginCommand(
            organization_code="hansung",
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
        identity_verifier=FakeIdentityVerifier(),
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
async def test_logout_deletes_refresh_token():
    auth_token_repository = InMemoryAuthTokenRepository()
    service = AuthService(
        organization_repository=InMemoryOrganizationRepository([
            make_organization()
        ]),
        user_repository=InMemoryUserRepository(),
        auth_token_repository=auth_token_repository,
        identity_verifier=FakeIdentityVerifier(),
    )

    tokens = await service.login(
        LoginCommand(
            organization_code="hansung",
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
