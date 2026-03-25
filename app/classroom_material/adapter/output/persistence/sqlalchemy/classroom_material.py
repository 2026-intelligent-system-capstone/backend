from collections.abc import Sequence
from uuid import UUID

from app.classroom_material.domain.entity import ClassroomMaterial
from app.classroom_material.domain.repository import ClassroomMaterialRepository
from core.db.session import session
from core.db.sqlalchemy.models.classroom_material import (
    classroom_material_table,
)
from sqlalchemy import select


class ClassroomMaterialSQLAlchemyRepository(ClassroomMaterialRepository):
    async def save(self, entity: ClassroomMaterial) -> ClassroomMaterial:
        return await session.merge(entity)

    async def get_by_id(self, entity_id: UUID) -> ClassroomMaterial | None:
        query = select(ClassroomMaterial).where(
            classroom_material_table.c.id == entity_id
        )
        result = await session.execute(query)
        return result.scalar_one_or_none()

    async def list(self) -> Sequence[ClassroomMaterial]:
        query = select(ClassroomMaterial).order_by(
            classroom_material_table.c.week.asc(),
            classroom_material_table.c.created_at.desc(),
        )
        result = await session.execute(query)
        return result.scalars().all()

    async def list_by_classroom(
        self,
        classroom_id: UUID,
    ) -> Sequence[ClassroomMaterial]:
        query = (
            select(ClassroomMaterial)
            .where(classroom_material_table.c.classroom_id == classroom_id)
            .order_by(
                classroom_material_table.c.week.asc(),
                classroom_material_table.c.created_at.desc(),
            )
        )
        result = await session.execute(query)
        return result.scalars().all()

    async def delete(self, entity: ClassroomMaterial) -> None:
        await session.delete(entity)
