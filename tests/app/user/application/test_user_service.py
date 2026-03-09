from uuid import UUID

import pytest

from app.user.application.dto.request import CreateUserRequest, UpdateUserRequest
from app.user.application.exceptions.user import (
    UserEmailAlreadyExistsException,
    UserNameAlreadyExistsException,
    UserNotFoundException,
)
from app.user.application.service.user import UserService
from app.user.domain.entity.user import User
from app.user.domain.repository.user import UserRepository


class InMemoryUserRepository(UserRepository):
    def __init__(self):
        self.users: dict[str, User] = {}

    async def save(self, entity: User) -> User:
        self.users[entity.email] = entity
        return entity

    async def get_by_id(self, user_id: UUID) -> User | None:
        return next((user for user in self.users.values() if user.id == user_id), None)

    async def get_by_username(self, username: str) -> User | None:
        return next((user for user in self.users.values() if user.username == username), None)

    async def get_by_email(self, email: str) -> User | None:
        return self.users.get(email)

    async def list(self) -> list[User]:
        return [user for user in self.users.values() if not user.is_deleted]


@pytest.mark.asyncio
async def test_create_user_success():
    repo = InMemoryUserRepository()
    service = UserService(user_repo=repo)

    request = CreateUserRequest(
        username="testuser",
        password="secure_password123",
        email="test@example.com",
        nickname="tester",
        real_name="김테스트",
        phone_number="010-1234-5678",
    )

    user = await service.create_user(request)

    assert user.email == "test@example.com"
    assert user.profile.real_name == "김테스트"
    assert user.password.startswith("$argon2")


@pytest.mark.asyncio
async def test_create_user_duplicate_username():
    repo = InMemoryUserRepository()
    service = UserService(user_repo=repo)

    first_request = CreateUserRequest(
        username="duplicate_user",
        password="secure_password123",
        email="first@example.com",
        nickname="tester",
        real_name="김테스트",
        phone_number="010-1234-5678",
    )
    second_request = CreateUserRequest(
        username="duplicate_user",
        password="secure_password123",
        email="second@example.com",
        nickname="tester2",
        real_name="김테스트2",
        phone_number="010-2222-3333",
    )

    await service.create_user(first_request)

    with pytest.raises(UserNameAlreadyExistsException):
        await service.create_user(second_request)


@pytest.mark.asyncio
async def test_create_user_duplicate_email():
    repo = InMemoryUserRepository()
    service = UserService(user_repo=repo)

    first_request = CreateUserRequest(
        username="firstuser",
        password="secure_password123",
        email="dup@example.com",
        nickname="tester",
        real_name="김테스트",
        phone_number="010-1234-5678",
    )
    second_request = CreateUserRequest(
        username="seconduser",
        password="secure_password123",
        email="dup@example.com",
        nickname="tester2",
        real_name="김테스트2",
        phone_number="010-2222-3333",
    )

    await service.create_user(first_request)

    with pytest.raises(UserEmailAlreadyExistsException):
        await service.create_user(second_request)


@pytest.mark.asyncio
async def test_get_user_not_found():
    repo = InMemoryUserRepository()
    service = UserService(user_repo=repo)

    with pytest.raises(UserNotFoundException):
        await service.get_user(UUID("00000000-0000-0000-0000-000000000000"))


@pytest.mark.asyncio
async def test_update_user_success():
    repo = InMemoryUserRepository()
    service = UserService(user_repo=repo)
    created_user = await service.create_user(
        CreateUserRequest(
            username="testuser",
            password="secure_password123",
            email="test@example.com",
            nickname="tester",
            real_name="김테스트",
            phone_number="010-1234-5678",
        )
    )

    updated_user = await service.update_user(
        created_user.id,
        UpdateUserRequest(nickname="updated", real_name="김업데이트", phone_number=None),
    )

    assert updated_user.profile.nickname == "updated"
    assert updated_user.profile.real_name == "김업데이트"
    assert updated_user.profile.phone_number is None


@pytest.mark.asyncio
async def test_update_user_duplicate_username():
    repo = InMemoryUserRepository()
    service = UserService(user_repo=repo)
    await service.create_user(
        CreateUserRequest(
            username="firstuser",
            password="secure_password123",
            email="first@example.com",
            nickname="tester",
            real_name="김테스트",
            phone_number="010-1234-5678",
        )
    )
    second_user = await service.create_user(
        CreateUserRequest(
            username="seconduser",
            password="secure_password123",
            email="second@example.com",
            nickname="tester2",
            real_name="김테스트2",
            phone_number="010-2222-3333",
        )
    )

    with pytest.raises(UserNameAlreadyExistsException):
        await service.update_user(second_user.id, UpdateUserRequest(username="firstuser"))


@pytest.mark.asyncio
async def test_delete_user_soft_delete():
    repo = InMemoryUserRepository()
    service = UserService(user_repo=repo)
    created_user = await service.create_user(
        CreateUserRequest(
            username="testuser",
            password="secure_password123",
            email="test@example.com",
            nickname="tester",
            real_name="김테스트",
            phone_number="010-1234-5678",
        )
    )

    deleted_user = await service.delete_user(created_user.id)

    assert deleted_user.is_deleted is True
