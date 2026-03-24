from abc import ABC, abstractmethod

from app.auth.domain.entity.authenticated_identity import AuthenticatedIdentity
from app.organization.domain.entity.organization import Organization


class IdentityVerifier(ABC):
    @abstractmethod
    async def verify(
        self,
        *,
        organization: Organization,
        login_id: str,
        password: str,
    ) -> AuthenticatedIdentity:
        """Verify user credentials against an organization identity system."""
