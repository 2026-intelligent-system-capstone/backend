from app.async_job.domain.entity import AsyncJob
from core.db.sqlalchemy.models.async_job import async_job_table

from .base import mapper_registry


def init_async_job_mappers():
    mapper_registry.map_imperatively(
        AsyncJob,
        async_job_table,
        version_id_col=async_job_table.c.version_id,
    )
