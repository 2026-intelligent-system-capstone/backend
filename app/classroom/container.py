from dependency_injector import containers, providers

from app.classroom.adapter.output.persistence.sqlalchemy import (
    ClassroomSQLAlchemyRepository,
)
from app.classroom.application.service import ClassroomService
from app.user.adapter.output.persistence.sqlalchemy import (
    UserSQLAlchemyRepository,
)


class ClassroomContainer(containers.DeclarativeContainer):
    wiring_config = containers.WiringConfiguration(
        modules=["app.classroom.adapter.input.api.v1.classroom"]
    )

    repository = providers.Singleton(ClassroomSQLAlchemyRepository)
    user_repository = providers.Singleton(UserSQLAlchemyRepository)
    service = providers.Factory(
        ClassroomService,
        repository=repository,
        user_repository=user_repository,
    )
