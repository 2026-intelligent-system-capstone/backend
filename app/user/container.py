from dependency_injector import containers, providers

from app.user.adapter.output.persistence.sqlalchemy.user import (
    UserSQLAlchemyRepository,
)
from app.user.application.service.user import UserService


class UserContainer(containers.DeclarativeContainer):
    wiring_config = containers.WiringConfiguration(
        modules=["app.user.adapter.input.api.v1.user"]
    )

    repository = providers.Singleton(UserSQLAlchemyRepository)
    service = providers.Factory(UserService, repository=repository)
