from app.classroom.domain.entity import Classroom
from core.db.sqlalchemy.models.classroom import classroom_table

from .base import mapper_registry


def init_classroom_mappers():
    mapper_registry.map_imperatively(
        Classroom,
        classroom_table,
        version_id_col=classroom_table.c.version_id,
    )
