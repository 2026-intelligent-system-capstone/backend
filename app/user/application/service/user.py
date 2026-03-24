from uuid import UUID

from app.user.application.exception import (
    UserAccountAlreadyExistsException,
    UserNotFoundException,
)
from app.user.domain.command import CreateUserCommand, UpdateUserCommand
from app.user.domain.entity.user import Profile, User
from app.user.domain.repository.user import UserRepository
from app.user.domain.usecase.user import UserUseCase
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

        profile = Profile(
            nickname=command.nickname,
            name=command.name,
            phone_number=command.phone_number,
        )
        user = User(
            organization_id=command.organization_id,
            login_id=command.login_id,
            role=command.role,
            email=command.email,
            profile=profile,
        )

        return await self.repository.save(user)

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
            user.login_id = command.login_id

        if "email" in delivered_fields:
            user.email = command.email

        if "role" in delivered_fields and command.role is not None:
            user.role = command.role

        if "status" in delivered_fields and command.status is not None:
            user.status = command.status

        nickname = user.profile.nickname
        if "nickname" in delivered_fields and command.nickname is not None:
            nickname = command.nickname

        name = user.profile.name
        if "name" in delivered_fields and command.name is not None:
            name = command.name

        phone_number = user.profile.phone_number
        if "phone_number" in delivered_fields:
            phone_number = command.phone_number

        user.profile = Profile(
            nickname=nickname,
            name=name,
            phone_number=phone_number,
            profile_image_id=user.profile.profile_image_id,
        )

        return await self.repository.save(user)

    @transactional
    async def delete_user(self, user_id: UUID) -> User:
        user = await self.repository.get_by_id(user_id)
        if user is None:
            raise UserNotFoundException()

        user.delete()
        return await self.repository.save(user)
