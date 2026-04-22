from uuid import UUID

from app.user.application.exception import (
    UserAccountAlreadyExistsException,
    UserNotFoundException,
)
from app.user.domain.command import CreateUserCommand, UpdateUserCommand
from app.user.domain.entity import User
from app.user.domain.repository import UserRepository
from app.user.domain.usecase import UserUseCase
from core.db.transactional import transactional


class UserService(UserUseCase):
    def __init__(self, *, repository: UserRepository):
        self.repository = repository

    @transactional
    async def create_user(self, command: CreateUserCommand) -> User:
        existing_user = await self.repository.get_by_organization_and_login_id(
            command.organization_id,
            command.login_id,
        )
        if existing_user:
            raise UserAccountAlreadyExistsException()

        user = User(
            organization_id=command.organization_id,
            login_id=command.login_id,
            role=command.role,
            email=command.email,
            name=command.name,
        )

        await self.repository.save(user)
        return user

    async def get_user(self, user_id: UUID) -> User:
        user = await self.repository.get_by_id(user_id)
        if user is None:
            raise UserNotFoundException()
        return user

    async def list_users(self) -> list[User]:
        return list(await self.repository.list())

    @transactional
    async def update_user(
        self, user_id: UUID, command: UpdateUserCommand
    ) -> User:
        user = await self.repository.get_by_id(user_id)
        if user is None:
            raise UserNotFoundException()

        delivered_fields = command.model_fields_set

        if (
            "login_id" in delivered_fields
            and command.login_id is not None
            and command.login_id != user.login_id
        ):
            existing_user = (
                await self.repository.get_by_organization_and_login_id(
                    user.organization_id,
                    command.login_id,
                )
            )
            if existing_user is not None and existing_user.id != user.id:
                raise UserAccountAlreadyExistsException()

        user.update(
            login_id=(
                command.login_id if "login_id" in delivered_fields else None
            ),
            role=(command.role if "role" in delivered_fields else None),
            email=(command.email if "email" in delivered_fields else None),
            clear_email=("email" in delivered_fields and command.email is None),
            name=(command.name if "name" in delivered_fields else None),
            status=(command.status if "status" in delivered_fields else None),
        )

        await self.repository.save(user)
        return user

    @transactional
    async def delete_user(self, user_id: UUID) -> User:
        user = await self.repository.get_by_id(user_id)
        if user is None:
            raise UserNotFoundException()

        user.delete()
        await self.repository.save(user)
        return user
