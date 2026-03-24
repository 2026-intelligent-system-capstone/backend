from dependency_injector import containers, providers

from app.organization.adapter.output.persistence.sqlalchemy import (
    OrganizationSQLAlchemyRepository,
)


class OrganizationContainer(containers.DeclarativeContainer):
    repository = providers.Singleton(OrganizationSQLAlchemyRepository)
