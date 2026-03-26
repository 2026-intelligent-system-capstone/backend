from uuid import UUID, uuid4

import pytest

from app.user.application.exception import (
    UserAccountAlreadyExistsException,
    UserNotFoundException,
)
from app.user.application.service import UserService
from app.user.domain.command import CreateUserCommand, UpdateUserCommand
from app.user.domain.entity import User, UserRole, UserStatus
from app.user.domain.repository import UserRepository

ORGANIZATION_ID = UUID("11111111-1111-1111-1111-111111111111")


class InMemoryUserRepository(UserRepository):
    def __init__(self):
        self.users: dict[UUID, User] = {}

    async def save(self, entity: User) -> None:
        self.users[entity.id] = entity

    async def get_by_id(self, entity_id: UUID) -> User | None:
        user = self.users.get(entity_id)
        if user is None or user.is_deleted:
            return None
        return user

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
                and not user.is_deleted
            ),
            None,
        )

    async def list_entities(self) -> list[User]:
        return [user for user in self.users.values() if not user.is_deleted]

    async def list_by_organization(
        self,
        organization_id: UUID,
    ) -> list[User]:
        return [
            user
            for user in self.users.values()
            if user.organization_id == organization_id and not user.is_deleted
        ]

    list = list_entities


@pytest.mark.asyncio
async def test_create_user_success():
    repo = InMemoryUserRepository()
    service = UserService(repository=repo)

    request = CreateUserCommand(
        organization_id=ORGANIZATION_ID,
        login_id="20260001",
        role=UserRole.STUDENT,
        email="test@example.com",
        name="김테스트",
    )

    user = await service.create_user(request)

    assert user.organization_id == ORGANIZATION_ID
    assert user.login_id == "20260001"
    assert user.name == "김테스트"


@pytest.mark.asyncio
async def test_create_user_duplicate_account():
    repo = InMemoryUserRepository()
    service = UserService(repository=repo)

    first_request = CreateUserCommand(
        organization_id=ORGANIZATION_ID,
        login_id="20260001",
        role=UserRole.STUDENT,
        email="first@example.com",
        name="김테스트",
    )
    second_request = CreateUserCommand(
        organization_id=ORGANIZATION_ID,
        login_id="20260001",
        role=UserRole.PROFESSOR,
        email="second@example.com",
        name="김테스트2",
    )

    await service.create_user(first_request)

    with pytest.raises(UserAccountAlreadyExistsException):
        await service.create_user(second_request)


@pytest.mark.asyncio
async def test_get_user_not_found():
    repo = InMemoryUserRepository()
    service = UserService(repository=repo)

    with pytest.raises(UserNotFoundException):
        await service.get_user(uuid4())


@pytest.mark.asyncio
async def test_get_user_success():
    repo = InMemoryUserRepository()
    service = UserService(repository=repo)
    created_user = await service.create_user(
        CreateUserCommand(
            organization_id=ORGANIZATION_ID,
            login_id="20260001",
            role=UserRole.STUDENT,
            email="test@example.com",
            name="김테스트",
        )
    )

    user = await service.get_user(created_user.id)

    assert user.id == created_user.id
    assert user.login_id == "20260001"


@pytest.mark.asyncio
async def test_list_users_excludes_deleted_users():
    repo = InMemoryUserRepository()
    service = UserService(repository=repo)
    active_user = await service.create_user(
        CreateUserCommand(
            organization_id=ORGANIZATION_ID,
            login_id="20260001",
            role=UserRole.STUDENT,
            email="active@example.com",
            name="활성 사용자",
        )
    )
    deleted_user = await service.create_user(
        CreateUserCommand(
            organization_id=ORGANIZATION_ID,
            login_id="20260002",
            role=UserRole.PROFESSOR,
            email="deleted@example.com",
            name="삭제 사용자",
        )
    )
    await service.delete_user(deleted_user.id)

    users = await service.list_users()

    assert [user.id for user in users] == [active_user.id]


@pytest.mark.asyncio
async def test_update_user_success():
    repo = InMemoryUserRepository()
    service = UserService(repository=repo)
    created_user = await service.create_user(
        CreateUserCommand(
            organization_id=ORGANIZATION_ID,
            login_id="20260001",
            role=UserRole.STUDENT,
            email="test@example.com",
            name="김테스트",
        )
    )

    updated_user = await service.update_user(
        created_user.id,
        UpdateUserCommand(
            name="김업데이트",
            role=UserRole.PROFESSOR,
        ),
    )

    assert updated_user.name == "김업데이트"
    assert updated_user.role == UserRole.PROFESSOR


@pytest.mark.asyncio
async def test_update_user_duplicate_login_id():
    repo = InMemoryUserRepository()
    service = UserService(repository=repo)
    await service.create_user(
        CreateUserCommand(
            organization_id=ORGANIZATION_ID,
            login_id="20260001",
            role=UserRole.STUDENT,
            email="first@example.com",
            name="김테스트",
        )
    )
    second_user = await service.create_user(
        CreateUserCommand(
            organization_id=ORGANIZATION_ID,
            login_id="20260002",
            role=UserRole.STUDENT,
            email="second@example.com",
            name="김테스트2",
        )
    )

    with pytest.raises(UserAccountAlreadyExistsException):
        await service.update_user(
            second_user.id,
            UpdateUserCommand(login_id="20260001"),
        )


@pytest.mark.asyncio
async def test_update_user_not_found():
    service = UserService(repository=InMemoryUserRepository())

    with pytest.raises(UserNotFoundException):
        await service.update_user(
            uuid4(), UpdateUserCommand(name="없는 사용자")
        )


@pytest.mark.asyncio
async def test_update_user_updates_email_and_status():
    repo = InMemoryUserRepository()
    service = UserService(repository=repo)
    created_user = await service.create_user(
        CreateUserCommand(
            organization_id=ORGANIZATION_ID,
            login_id="20260001",
            role=UserRole.STUDENT,
            email="before@example.com",
            name="김테스트",
        )
    )

    updated_user = await service.update_user(
        created_user.id,
        UpdateUserCommand(
            email="after@example.com",
            status=UserStatus.BLOCKED,
        ),
    )

    assert updated_user.email == "after@example.com"
    assert updated_user.status == UserStatus.BLOCKED


@pytest.mark.asyncio
async def test_update_user_omitted_fields_remain_unchanged():
    repo = InMemoryUserRepository()
    service = UserService(repository=repo)
    created_user = await service.create_user(
        CreateUserCommand(
            organization_id=ORGANIZATION_ID,
            login_id="20260001",
            role=UserRole.STUDENT,
            email="test@example.com",
            name="김테스트",
        )
    )

    updated_user = await service.update_user(
        created_user.id,
        UpdateUserCommand(name="이름만변경"),
    )

    assert updated_user.name == "이름만변경"
    assert updated_user.email == "test@example.com"
    assert updated_user.role == UserRole.STUDENT


@pytest.mark.asyncio
async def test_delete_user_soft_delete():
    repo = InMemoryUserRepository()
    service = UserService(repository=repo)
    created_user = await service.create_user(
        CreateUserCommand(
            organization_id=ORGANIZATION_ID,
            login_id="20260001",
            role=UserRole.STUDENT,
            email="test@example.com",
            name="김테스트",
        )
    )

    deleted_user = await service.delete_user(created_user.id)

    assert deleted_user.is_deleted is True


@pytest.mark.asyncio
async def test_delete_user_not_found():
    service = UserService(repository=InMemoryUserRepository())

    with pytest.raises(UserNotFoundException):
        await service.delete_user(uuid4())
