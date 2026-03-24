from dependency_injector import containers, providers
from valkey.asyncio import from_url

from app.auth.adapter.output.integration.hansung_identity_verifier import (
    HansungIdentityVerifier,
)
from app.auth.adapter.output.persistence.valkey.auth_token import (
    ValkeyAuthTokenRepository,
)
from app.auth.application.service.auth import AuthService
from app.organization.adapter.output.persistence.sqlalchemy import (
    OrganizationSQLAlchemyRepository,
)
from app.user.adapter.output.persistence.sqlalchemy.user import (
    UserSQLAlchemyRepository,
)
from core.config import config


class AuthContainer(containers.DeclarativeContainer):
    wiring_config = containers.WiringConfiguration(
        modules=["app.auth.adapter.input.api.v1.auth"]
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
    organization_repository = providers.Singleton(
        OrganizationSQLAlchemyRepository
    )
    user_repository = providers.Singleton(UserSQLAlchemyRepository)
    identity_verifier = providers.Singleton(HansungIdentityVerifier)
    service = providers.Factory(
        AuthService,
        organization_repository=organization_repository,
        user_repository=user_repository,
        auth_token_repository=auth_token_repository,
        identity_verifier=identity_verifier,
    )
