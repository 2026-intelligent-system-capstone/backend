from uuid import UUID

import pytest

from app.user.application.dto.request import CreateUserRequest
from app.user.application.exceptions.user import UserEmailAlreadyExistsException
from app.user.application.service.user import UserService
from app.user.domain.entity.user import User
from app.user.domain.repository.user import UserRepository


class InMemoryUserRepository(UserRepository):
    def __init__(self):
        self.users = {}

    async def save(self, entity: User) -> User:
        self.users[entity.email] = entity
        return entity

    async def get_by_id(self, user_id: UUID):
        _ = user_id
        return None

    async def get_by_email(self, email: str):
        return self.users.get(email)

    async def list(self):
        return list(self.users.values())


@pytest.mark.asyncio
async def test_create_user_success():
    repo = InMemoryUserRepository()
    service = UserService(user_repo=repo)

    req = CreateUserRequest(
        username="testuser",
        password="secure_password123",
        email="test@example.com",
        nickname="tester",
        real_name="김테스트",
        phone_number="010-1234-5678",
    )

    user = await service.create_user(req)

    assert user.email == "test@example.com"
    assert user.profile.real_name == "김테스트"
    assert user.password.startswith("$argon2")


@pytest.mark.asyncio
async def test_create_user_duplicate_email():
    repo = InMemoryUserRepository()
    service = UserService(user_repo=repo)

    req = CreateUserRequest(
        username="testuser",
        password="secure_password123",
        email="dup@example.com",
        nickname="tester",
        real_name="김테스트",
        phone_number="010-1234-5678",
    )

    await service.create_user(req)

    with pytest.raises(UserEmailAlreadyExistsException):
        await service.create_user(req)
