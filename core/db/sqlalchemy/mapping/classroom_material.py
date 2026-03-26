from app.classroom_material.domain.entity import ClassroomMaterial
from core.db.sqlalchemy.models.classroom_material import (
    classroom_material_table,
)

from .base import mapper_registry


def init_classroom_material_mappers():
    mapper_registry.map_imperatively(
        ClassroomMaterial,
        classroom_material_table,
        version_id_col=classroom_material_table.c.version_id,
    )
