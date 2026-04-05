from dependency_injector import containers, providers

from app.classroom.adapter.output.integration import (
    LLMClassroomMaterialIngestAdapter,
)
from app.classroom.adapter.output.persistence.sqlalchemy import (
    ClassroomMaterialSQLAlchemyRepository,
    ClassroomSQLAlchemyRepository,
)
from app.classroom.application.service import ClassroomService
from app.file.container import FileContainer
from app.user.adapter.output.persistence.sqlalchemy import (
    UserSQLAlchemyRepository,
)


class ClassroomContainer(containers.DeclarativeContainer):
    wiring_config = containers.WiringConfiguration(
        modules=[
            "app.classroom.adapter.input.api.v1.classroom",
            "app.classroom.adapter.input.api.v1.material",
        ]
    )

    repository = providers.Singleton(ClassroomSQLAlchemyRepository)
    user_repository = providers.Singleton(UserSQLAlchemyRepository)
    material_repository = providers.Singleton(
        ClassroomMaterialSQLAlchemyRepository
    )
    material_ingest_port = providers.Singleton(
        LLMClassroomMaterialIngestAdapter
    )
    service = providers.Factory(
        ClassroomService,
        repository=repository,
        user_repository=user_repository,
        material_repository=material_repository,
        file_usecase=FileContainer.service,
        material_ingest_port=material_ingest_port,
    )
