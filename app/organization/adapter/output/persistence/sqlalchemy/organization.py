from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import select

from app.organization.domain.entity.organization import Organization
from app.organization.domain.repository.organization import (
    OrganizationRepository,
)
from core.db.session import session
from core.db.sqlalchemy.models.organization import organization_table


class OrganizationSQLAlchemyRepository(OrganizationRepository):
    async def get_by_id(self, entity_id: UUID) -> Organization | None:
        query = select(Organization).where(organization_table.c.id == entity_id)
        result = await session.execute(query)
        return result.scalar_one_or_none()

    async def get_by_code(self, code: str) -> Organization | None:
        query = select(Organization).where(organization_table.c.code == code)
        result = await session.execute(query)
        return result.scalar_one_or_none()

    async def list(self) -> Sequence[Organization]:
        query = select(Organization).order_by(organization_table.c.name.asc())
        result = await session.execute(query)
        return result.scalars().all()

    async def save(self, entity: Organization) -> Organization:
        session.add(entity)
        return entity
