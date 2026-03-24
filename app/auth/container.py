from dependency_injector import containers, providers
from valkey.asyncio import from_url

from app.auth.adapter.output.persistence.valkey.auth_token import (
    ValkeyAuthTokenRepository,
)
from app.auth.application.service import AuthService
from app.organization.container import OrganizationContainer
from app.user.adapter.output.persistence.sqlalchemy import (
    UserSQLAlchemyRepository,
)
from core.config import config


class AuthContainer(containers.DeclarativeContainer):
    wiring_config = containers.WiringConfiguration(
        modules=[
            "app.auth.adapter.input.api.v1.auth",
            "app.auth.adapter.input.api.v1.deps",
        ]
    )

    valkey_client = providers.Singleton(
        from_url,
        config.VALKEY_URL,
        decode_responses=True,
    )
    auth_token_repository = providers.Singleton(
        ValkeyAuthTokenRepository,
        client=valkey_client,
    )
    organization = providers.Container(OrganizationContainer)
    organization_repository = organization.repository
    user_repository = providers.Singleton(UserSQLAlchemyRepository)
    organization_auth_service = organization.auth_service
    service = providers.Factory(
        AuthService,
        organization_repository=organization_repository,
        user_repository=user_repository,
        auth_token_repository=auth_token_repository,
        organization_auth_service=organization_auth_service,
    )
