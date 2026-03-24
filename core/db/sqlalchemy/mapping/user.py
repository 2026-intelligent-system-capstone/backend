from sqlalchemy.orm import composite

from app.user.domain.entity.user import Profile, User
from core.db.sqlalchemy.models.user import user_table

from .base import mapper_registry


def init_user_mappers():
    mapper_registry.map_imperatively(
        User,
        user_table,
        properties={
            "profile": composite(
                Profile,
                user_table.c.nickname,
                user_table.c.real_name,
                user_table.c.phone_number,
                user_table.c.profile_image_id,
            )
        },
        version_id_col=user_table.c.version_id,
    )
