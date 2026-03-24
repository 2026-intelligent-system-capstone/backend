from app.auth.application.exception import (
    AuthIdentityProviderNotConfiguredException,
)
from app.organization.domain.entity import (
    Organization,
    OrganizationAuthProvider,
)
from app.organization.domain.service import OrganizationAuthService


class OrganizationIdentityService(OrganizationAuthService):
    def __init__(self, *, hansung: OrganizationAuthService):
        self.hansung = hansung

    async def authenticate(
        self,
        *,
        organization: Organization,
        login_id: str,
        password: str,
    ):
        if organization.auth_provider == OrganizationAuthProvider.HANSUNG_SIS:
            return await self.hansung.authenticate(
                organization=organization,
                login_id=login_id,
                password=password,
            )

        raise AuthIdentityProviderNotConfiguredException(
            detail={
                "organization_code": organization.code,
                "auth_provider": organization.auth_provider.value,
            }
        )
