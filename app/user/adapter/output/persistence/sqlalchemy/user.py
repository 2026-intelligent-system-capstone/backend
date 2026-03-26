from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import select

from app.user.domain.entity import User
from app.user.domain.repository import UserRepository
from core.db.session import session
from core.db.sqlalchemy.models.user import user_table


class UserSQLAlchemyRepository(UserRepository):
    async def get_by_id(self, entity_id: UUID) -> User | None:
        query = select(User).where(
            user_table.c.id == entity_id,
            user_table.c.is_deleted.is_(False),
        )
        result = await session.execute(query)
        return result.scalar_one_or_none()

    async def get_by_organization_and_login_id(
        self,
        organization_id: UUID,
        login_id: str,
    ) -> User | None:
        query = select(User).where(
            user_table.c.organization_id == organization_id,
            user_table.c.login_id == login_id,
            user_table.c.is_deleted.is_(False),
        )
        result = await session.execute(query)
        return result.scalar_one_or_none()

    async def list(self) -> Sequence[User]:
        query = select(User).where(user_table.c.is_deleted.is_(False))
        result = await session.execute(query)
        return result.scalars().all()

    async def list_by_organization(
        self,
        organization_id: UUID,
    ) -> Sequence[User]:
        query = select(User).where(
            user_table.c.organization_id == organization_id,
            user_table.c.is_deleted.is_(False),
        )
        result = await session.execute(query)
        return result.scalars().all()

    async def save(self, entity: User) -> None:
        session.add(entity)
