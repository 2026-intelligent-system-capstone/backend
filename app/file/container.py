from dependency_injector import containers, providers

from app.file.adapter.output.persistence.sqlalchemy.file import (
    FileSQLAlchemyRepository,
)
from app.file.adapter.output.storage import R2FileStorage
from app.file.application.service.file import FileService


class FileContainer(containers.DeclarativeContainer):
    wiring_config = containers.WiringConfiguration(
        modules=["app.file.adapter.input.api.v1.file"]
    )

    repository = providers.Singleton(FileSQLAlchemyRepository)
    storage = providers.Singleton(R2FileStorage)
    service = providers.Factory(
        FileService,
        repository=repository,
        storage=storage,
    )
