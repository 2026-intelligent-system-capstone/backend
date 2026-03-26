from types import SimpleNamespace
from uuid import UUID

import pytest
from fastapi import Request

from app.auth.application.exception import (
    AuthForbiddenException,
    AuthUnauthorizedException,
)
from app.auth.domain.entity import CurrentUser, RequestUser
from app.user.domain.entity import User, UserRole, UserStatus
from app.user.domain.repository import UserRepository
from core.fastapi.dependencies.permission import (
    IsAdmin,
    IsProfessorOrAdmin,
    PermissionDependency,
    get_current_user,
    get_user_repository,
)

ORGANIZATION_ID = UUID("11111111-1111-1111-1111-111111111111")
USER_ID = UUID("22222222-2222-2222-2222-222222222222")


class InMemoryUserRepository(UserRepository):
    def __init__(self, users: list[User] | None = None):
        self.users = {user.id: user for user in users or []}

    async def save(self, entity: User) -> None:
        self.users[entity.id] = entity

    async def get_by_id(self, entity_id: UUID) -> User | None:
        return self.users.get(entity_id)

    async def list_entities(self) -> list[User]:
        return list(self.users.values())

    async def list_by_organization(
        self,
        organization_id: UUID,
    ) -> list[User]:
        return [
            user
            for user in self.users.values()
            if user.organization_id == organization_id
        ]

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

    list = list_entities


def make_user(
    *,
    role: UserRole = UserRole.STUDENT,
    status: UserStatus = UserStatus.ACTIVE,
) -> User:
    user = User(
        organization_id=ORGANIZATION_ID,
        login_id="20260001",
        role=role,
        email="student@example.com",
        name="김테스트",
        status=status,
    )
    user.id = USER_ID
    return user


def make_request(
    *,
    user: RequestUser | None = None,
    current_user: CurrentUser | None = None,
    repository: UserRepository | None = None,
) -> Request:
    request = Request({
        "type": "http",
        "headers": [],
        "app": SimpleNamespace(
            container=SimpleNamespace(
                user=SimpleNamespace(
                    repository=lambda: repository,
                )
            )
        ),
        "user": user or RequestUser(),
        "state": {},
    })
    if current_user is not None:
        request.state.current_user = current_user
    return request


@pytest.mark.asyncio
async def test_get_current_user_sets_request_state_from_repository_user():
    repository = InMemoryUserRepository([make_user(role=UserRole.ADMIN)])
    request = make_request(
        user=RequestUser(id=USER_ID),
        repository=repository,
    )

    current_user = await get_current_user(request, repository)

    assert current_user == CurrentUser(
        id=USER_ID,
        organization_id=ORGANIZATION_ID,
        login_id="20260001",
        role=UserRole.ADMIN,
    )
    assert request.state.current_user == current_user


@pytest.mark.asyncio
async def test_get_current_user_raises_when_request_user_missing():
    request = make_request(repository=InMemoryUserRepository())

    with pytest.raises(AuthUnauthorizedException):
        await get_current_user(request, InMemoryUserRepository())


@pytest.mark.asyncio
async def test_get_current_user_raises_for_blocked_user():
    repository = InMemoryUserRepository([make_user(status=UserStatus.BLOCKED)])
    request = make_request(
        user=RequestUser(id=USER_ID),
        repository=repository,
    )

    with pytest.raises(AuthUnauthorizedException):
        await get_current_user(request, repository)


@pytest.mark.asyncio
async def test_permission_dependency_raises_for_non_admin_user():
    current_user = CurrentUser(
        id=USER_ID,
        organization_id=ORGANIZATION_ID,
        login_id="20260001",
        role=UserRole.STUDENT,
    )
    request = make_request(current_user=current_user)

    with pytest.raises(AuthForbiddenException):
        await PermissionDependency([IsAdmin])(request, current_user)


@pytest.mark.asyncio
async def test_permission_dependency_allows_professor_for_professor_or_admin():
    current_user = CurrentUser(
        id=USER_ID,
        organization_id=ORGANIZATION_ID,
        login_id="20260001",
        role=UserRole.PROFESSOR,
    )
    request = make_request(current_user=current_user)

    await PermissionDependency([IsProfessorOrAdmin])(request, current_user)


def test_get_user_repository_returns_repository_from_container():
    repository = InMemoryUserRepository()
    request = make_request(repository=repository)

    resolved_repository = get_user_repository(request)

    assert resolved_repository is repository
