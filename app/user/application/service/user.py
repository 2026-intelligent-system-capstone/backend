from uuid import UUID

from app.user.application.dto.request import CreateUserRequest, UpdateUserRequest
from app.user.application.exceptions.user import (
    UserEmailAlreadyExistsException,
    UserNameAlreadyExistsException,
    UserNotFoundException,
)
from app.user.domain.entity.user import Profile, User
from app.user.domain.repository.user import UserRepository
from core.db.transactional import transactional
from core.helpers.argon2 import Argon2Helper


class UserService:
    def __init__(self, user_repo: UserRepository):
        self.user_repo = user_repo

    @transactional
    async def create_user(self, request: CreateUserRequest) -> User:
        existing_user = await self.user_repo.get_by_username(request.username)
        if existing_user:
            raise UserNameAlreadyExistsException()

        existing_user = await self.user_repo.get_by_email(request.email)
        if existing_user:
            raise UserEmailAlreadyExistsException()

        hashed_password = Argon2Helper.hash(request.password)
        profile = Profile(nickname=request.nickname, real_name=request.real_name, phone_number=request.phone_number)
        user = User(username=request.username, password=hashed_password, email=request.email, profile=profile)

        return await self.user_repo.save(user)

    async def get_user(self, user_id: UUID) -> User:
        user = await self.user_repo.get_by_id(user_id)
        if user is None:
            raise UserNotFoundException()
        return user

    async def list_users(self) -> list[User]:
        return list(await self.user_repo.list())

    @transactional
    async def update_user(self, user_id: UUID, request: UpdateUserRequest) -> User:
        user = await self.user_repo.get_by_id(user_id)
        if user is None:
            raise UserNotFoundException()

        if request.username is not None and request.username != user.username:
            existing_user = await self.user_repo.get_by_username(request.username)
            if existing_user is not None and existing_user.id != user.id:
                raise UserNameAlreadyExistsException()
            user.username = request.username

        if request.email is not None and request.email != user.email:
            existing_user = await self.user_repo.get_by_email(request.email)
            if existing_user is not None and existing_user.id != user.id:
                raise UserEmailAlreadyExistsException()
            user.email = request.email

        if request.password is not None:
            user.password = Argon2Helper.hash(request.password)

        phone_number = (
            request.phone_number
            if "phone_number" in request.model_fields_set
            else user.profile.phone_number
        )
        user.profile = Profile(
            nickname=request.nickname if request.nickname is not None else user.profile.nickname,
            real_name=request.real_name if request.real_name is not None else user.profile.real_name,
            phone_number=phone_number,
            profile_image_id=user.profile.profile_image_id,
        )

        return await self.user_repo.save(user)

    @transactional
    async def delete_user(self, user_id: UUID) -> User:
        user = await self.user_repo.get_by_id(user_id)
        if user is None:
            raise UserNotFoundException()

        user.delete()
        return await self.user_repo.save(user)
