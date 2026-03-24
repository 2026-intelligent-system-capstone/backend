from uuid import UUID

from app.user.application.exception import (
    UserEmailAlreadyExistsException,
    UserNameAlreadyExistsException,
    UserNotFoundException,
)
from app.user.domain.command import CreateUserCommand, UpdateUserCommand
from app.user.domain.entity.user import Profile, User
from app.user.domain.repository.user import UserRepository
from app.user.domain.usecase.user import UserUseCase
from core.db.transactional import transactional
from core.helpers.argon2 import Argon2Helper


class UserService(UserUseCase):
    def __init__(self, *, repository: UserRepository):
        self.repository = repository

    @transactional
    async def create_user(self, command: CreateUserCommand) -> User:
        existing_user = await self.repository.get_by_username(command.username)
        if existing_user:
            raise UserNameAlreadyExistsException()

        existing_user = await self.repository.get_by_email(command.email)
        if existing_user:
            raise UserEmailAlreadyExistsException()

        hashed_password = Argon2Helper.hash(command.password)
        profile = Profile(
            nickname=command.nickname,
            real_name=command.real_name,
            phone_number=command.phone_number,
        )
        user = User(
            username=command.username,
            password=hashed_password,
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
            "username" in delivered_fields
            and command.username is not None
            and command.username != user.username
        ):
            existing_user = await self.repository.get_by_username(
                command.username
            )
            if existing_user is not None and existing_user.id != user.id:
                raise UserNameAlreadyExistsException()
            user.username = command.username

        if (
            "email" in delivered_fields
            and command.email is not None
            and command.email != user.email
        ):
            existing_user = await self.repository.get_by_email(command.email)
            if existing_user is not None and existing_user.id != user.id:
                raise UserEmailAlreadyExistsException()
            user.email = command.email

        if "password" in delivered_fields and command.password is not None:
            user.password = Argon2Helper.hash(command.password)

        nickname = user.profile.nickname
        if "nickname" in delivered_fields and command.nickname is not None:
            nickname = command.nickname

        real_name = user.profile.real_name
        if "real_name" in delivered_fields and command.real_name is not None:
            real_name = command.real_name

        phone_number = user.profile.phone_number
        if "phone_number" in delivered_fields:
            phone_number = command.phone_number

        user.profile = Profile(
            nickname=nickname,
            real_name=real_name,
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
