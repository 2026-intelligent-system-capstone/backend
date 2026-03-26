from dependency_injector import containers, providers

from app.classroom.container import ClassroomContainer
from app.classroom_material.adapter.output.persistence.sqlalchemy import (
    ClassroomMaterialSQLAlchemyRepository,
)
from app.classroom_material.application.service import ClassroomMaterialService
from app.file.container import FileContainer


class ClassroomMaterialContainer(containers.DeclarativeContainer):
    wiring_config = containers.WiringConfiguration(
        modules=[
            "app.classroom_material.adapter.input.api.v1.classroom_material"
        ]
    )

    repository = providers.Singleton(ClassroomMaterialSQLAlchemyRepository)
    service = providers.Factory(
        ClassroomMaterialService,
        repository=repository,
        classroom_usecase=ClassroomContainer.service,
        file_usecase=FileContainer.service,
    )
