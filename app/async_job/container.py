from dependency_injector import containers, providers

from app.async_job.adapter.output.persistence.sqlalchemy import (
    AsyncJobSQLAlchemyRepository,
)
from app.async_job.application.service import AsyncJobService


class AsyncJobContainer(containers.DeclarativeContainer):
    repository = providers.Singleton(AsyncJobSQLAlchemyRepository)
    service = providers.Singleton(
        AsyncJobService,
        repository=repository,
    )
