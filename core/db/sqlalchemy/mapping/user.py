from app.user.domain.entity import User
from core.db.sqlalchemy.models.user import user_table

from .base import mapper_registry


def init_user_mappers():
    mapper_registry.map_imperatively(
        User,
        user_table,
        version_id_col=user_table.c.version_id,
    )
