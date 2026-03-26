from abc import ABC, abstractmethod

from app.organization.domain.entity import Organization, OrganizationIdentity


class OrganizationAuthService(ABC):
    @abstractmethod
    async def authenticate(
        self,
        *,
        organization: Organization,
        login_id: str,
        password: str,
    ) -> OrganizationIdentity:
        """Authenticate against an organization identity provider."""
