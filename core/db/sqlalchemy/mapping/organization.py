from app.organization.domain.entity import Organization
from core.db.sqlalchemy.models.organization import organization_table

from .base import mapper_registry


def init_organization_mappers():
    mapper_registry.map_imperatively(
        Organization,
        organization_table,
        version_id_col=organization_table.c.version_id,
    )
