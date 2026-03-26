from abc import ABC, abstractmethod
from uuid import UUID

from app.organization.domain.command import (
    CreateOrganizationCommand,
    UpdateOrganizationCommand,
)
from app.organization.domain.entity import Organization


class OrganizationUseCase(ABC):
    @abstractmethod
    async def create_organization(
        self,
        command: CreateOrganizationCommand,
    ) -> Organization:
        """Create organization."""

    @abstractmethod
    async def get_organization(self, organization_id: UUID) -> Organization:
        """Get organization."""

    @abstractmethod
    async def list_organizations(self) -> list[Organization]:
        """List organizations."""

    @abstractmethod
    async def update_organization(
        self,
        organization_id: UUID,
        command: UpdateOrganizationCommand,
    ) -> Organization:
        """Update organization."""

    @abstractmethod
    async def delete_organization(self, organization_id: UUID) -> Organization:
        """Delete organization."""
