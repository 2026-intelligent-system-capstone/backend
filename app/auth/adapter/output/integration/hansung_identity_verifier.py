from app.auth.application.exception import (
    AuthIdentityProviderNotConfiguredException,
)
from app.auth.domain.entity.authenticated_identity import AuthenticatedIdentity
from app.auth.domain.repository.identity_verifier import IdentityVerifier
from app.organization.domain.entity.organization import (
    Organization,
    OrganizationAuthProvider,
)


class HansungIdentityVerifier(IdentityVerifier):
    async def verify(
        self,
        *,
        organization: Organization,
        login_id: str,
        password: str,
    ) -> AuthenticatedIdentity:
        del login_id
        del password

        if organization.auth_provider != OrganizationAuthProvider.HANSUNG_SIS:
            raise AuthIdentityProviderNotConfiguredException()

        raise AuthIdentityProviderNotConfiguredException(
            detail={
                "organization_code": organization.code,
                "reason": (
                    "Hansung SIS integration details are not configured yet."
                ),
            }
        )
