from typing import Sequence
from sqlalchemy import select, update
from app.user.domain.entity.user import User, Profile, UserStatus
from app.user.domain.repository.user import UserRepository
from app.user.adapter.output.persistence.model import UserModel
from core.db.session import session

class UserPersistenceAdapter(UserRepository):
    def _entity_to_model(self, user: User) -> UserModel:
        return UserModel(
            id=user.id,
            username=user.username,
            password=user.password,
            email=user.email,
            nickname=user.profile.nickname,
            real_name=user.profile.real_name,
            phone_number=user.profile.phone_number,
            profile_image_id=user.profile.profile_image_id,
            status=user.status,
            is_deleted=user.is_deleted
        )

    def _model_to_entity(self, model: UserModel) -> User:
        return User(
            id=model.id,
            username=model.username,
            password=model.password,
            email=model.email,
            profile=Profile(
                nickname=model.nickname,
                real_name=model.real_name,
                phone_number=model.phone_number,
                profile_image_id=model.profile_image_id
            ),
            status=model.status,
            is_deleted=model.is_deleted
        )

    async def save(self, user: User) -> User:
        model = self._entity_to_model(user)
        # Use merge to handle both insert and update
        merged_model = await session.merge(model)
        await session.flush()
        return self._model_to_entity(merged_model)

    async def get_by_id(self, id: any) -> User | None:
        query = select(UserModel).where(UserModel.id == id, UserModel.is_deleted == False)
        result = await session.execute(query)
        model = result.scalar_one_of_none()
        return self._model_to_entity(model) if model else None

    async def get_by_email(self, email: str) -> User | None:
        query = select(UserModel).where(UserModel.email == email, UserModel.is_deleted == False)
        result = await session.execute(query)
        model = result.scalar_one_of_none()
        return self._model_to_entity(model) if model else None

    async def list(self) -> Sequence[User]:
        query = select(UserModel).where(UserModel.is_deleted == False)
        result = await session.execute(query)
        models = result.scalars().all()
        return [self._model_to_entity(m) for m in models]

    async def delete(self, user: User) -> None:
        # Soft delete is handled by the entity logic (status change), 
        # so we just sync the state to DB.
        model = self._entity_to_model(user)
        await session.merge(model)
        await session.flush()
