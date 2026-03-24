from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import select

from app.user.domain.entity.user import User
from app.user.domain.repository.user import UserRepository
from core.db.session import session
from core.db.sqlalchemy.models.user import user_table


class UserSQLAlchemyRepository(UserRepository):
    async def get_by_id(self, user_id: UUID) -> User | None:
        query = select(User).where(
            user_table.c.id == user_id,
            user_table.c.is_deleted.is_(False),
        )
        result = await session.execute(query)
        return result.scalar_one_or_none()

    async def get_by_username(self, username: str) -> User | None:
        query = select(User).where(
            user_table.c.username == username,
            user_table.c.is_deleted.is_(False),
        )
        result = await session.execute(query)
        return result.scalar_one_or_none()

    async def get_by_email(self, email: str) -> User | None:
        query = select(User).where(
            user_table.c.email == email,
            user_table.c.is_deleted.is_(False),
        )
        result = await session.execute(query)
        return result.scalar_one_or_none()

    async def list(self) -> Sequence[User]:
        query = select(User).where(user_table.c.is_deleted.is_(False))
        result = await session.execute(query)
        return result.scalars().all()

    async def save(self, user: User) -> User:
        session.add(user)
        return user
