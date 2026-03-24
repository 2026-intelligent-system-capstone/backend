from app.file.domain.entity.file import File
from core.db.sqlalchemy.models.file import file_table

from .base import mapper_registry


def init_file_mappers():
    mapper_registry.map_imperatively(
        File,
        file_table,
        version_id_col=file_table.c.version_id,
    )
