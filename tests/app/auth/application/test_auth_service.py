from uuid import UUID, uuid4

import pytest

from app.auth.application.exception import (
    AuthInvalidCredentialsException,
    AuthInvalidRefreshTokenException,
)
from app.auth.application.service.auth import AuthService
from app.auth.domain.command import (
    LoginCommand,
    LogoutCommand,
    RefreshTokenCommand,
)
from app.auth.domain.repository.auth_token import AuthTokenRepository
from app.user.domain.entity.user import Profile, User
from app.user.domain.repository.user import UserRepository
from core.domain.types import TokenType
from core.helpers.argon2 import Argon2Helper
from core.helpers.token import TokenHelper


class InMemoryUserRepository(UserRepository):
    def __init__(self, users: list[User] | None = None):
        self.users = {user.id: user for user in users or []}

    async def save(self, entity: User) -> User:
        self.users[entity.id] = entity
        return entity

    async def get_by_id(self, entity_id: UUID) -> User | None:
        return self.users.get(entity_id)

    async def list(self) -> list[User]:
        return list(self.users.values())

    async def get_by_username(self, username: str) -> User | None:
        return next(
            (user for user in self.users.values() if user.username == username),
            None,
        )

    async def get_by_email(self, email: str) -> User | None:
        return next(
            (user for user in self.users.values() if user.email == email), None
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


def make_user(
    email: str = "auth@example.com", password: str = "secure_password123"
) -> User:
    return User(
        username="authuser",
        password=Argon2Helper.hash(password),
        email=email,
        profile=Profile(nickname="auth", real_name="김인증"),
    )


@pytest.mark.asyncio
async def test_login_success_issues_and_stores_tokens():
    user = make_user()
    user_repository = InMemoryUserRepository([user])
    auth_token_repository = InMemoryAuthTokenRepository()
    service = AuthService(
        user_repository=user_repository,
        auth_token_repository=auth_token_repository,
    )

    tokens = await service.login(
        LoginCommand(email="auth@example.com", password="secure_password123")
    )

    refresh_payload = TokenHelper.decode_token(tokens.refresh_token)
    stored_token = await auth_token_repository.get(
        user_id=user.id,
        jti=refresh_payload["jti"],
    )
    assert tokens.user_id == str(user.id)
    assert stored_token == tokens.refresh_token


@pytest.mark.asyncio
async def test_login_invalid_password_raises():
    user = make_user()
    service = AuthService(
        user_repository=InMemoryUserRepository([user]),
        auth_token_repository=InMemoryAuthTokenRepository(),
    )

    with pytest.raises(AuthInvalidCredentialsException):
        await service.login(
            LoginCommand(email="auth@example.com", password="wrong_password")
        )


@pytest.mark.asyncio
async def test_refresh_rotates_refresh_token():
    user = make_user()
    auth_token_repository = InMemoryAuthTokenRepository()
    service = AuthService(
        user_repository=InMemoryUserRepository([user]),
        auth_token_repository=auth_token_repository,
    )

    first_tokens = await service.login(
        LoginCommand(email="auth@example.com", password="secure_password123")
    )
    first_payload = TokenHelper.decode_token(first_tokens.refresh_token)

    refreshed_tokens = await service.refresh(
        RefreshTokenCommand(refresh_token=first_tokens.refresh_token)
    )
    refreshed_payload = TokenHelper.decode_token(refreshed_tokens.refresh_token)

    assert refreshed_tokens.refresh_token != first_tokens.refresh_token
    assert (
        await auth_token_repository.get(
            user_id=user.id, jti=first_payload["jti"]
        )
        is None
    )
    assert (
        await auth_token_repository.get(
            user_id=user.id, jti=refreshed_payload["jti"]
        )
        == refreshed_tokens.refresh_token
    )


@pytest.mark.asyncio
async def test_refresh_with_unknown_token_raises():
    service = AuthService(
        user_repository=InMemoryUserRepository(),
        auth_token_repository=InMemoryAuthTokenRepository(),
    )

    invalid_refresh = TokenHelper.create_token(
        payload={"sub": str(uuid4()), "jti": str(uuid4())},
        token_type=TokenType.REFRESH,
    )

    with pytest.raises(AuthInvalidRefreshTokenException):
        await service.refresh(
            RefreshTokenCommand(refresh_token=invalid_refresh)
        )


@pytest.mark.asyncio
async def test_refresh_without_token_raises():
    service = AuthService(
        user_repository=InMemoryUserRepository(),
        auth_token_repository=InMemoryAuthTokenRepository(),
    )

    with pytest.raises(AuthInvalidRefreshTokenException):
        await service.refresh(RefreshTokenCommand())


@pytest.mark.asyncio
async def test_logout_deletes_refresh_token():
    user = make_user()
    auth_token_repository = InMemoryAuthTokenRepository()
    service = AuthService(
        user_repository=InMemoryUserRepository([user]),
        auth_token_repository=auth_token_repository,
    )

    tokens = await service.login(
        LoginCommand(email="auth@example.com", password="secure_password123")
    )
    refresh_payload = TokenHelper.decode_token(tokens.refresh_token)

    await service.logout(LogoutCommand(refresh_token=tokens.refresh_token))

    assert (
        await auth_token_repository.get(
            user_id=user.id, jti=refresh_payload["jti"]
        )
        is None
    )
