from uuid import UUID

from app.organization.application.exception import (
    OrganizationCodeAlreadyExistsException,
    OrganizationNotFoundException,
)
from app.organization.domain.command import (
    CreateOrganizationCommand,
    UpdateOrganizationCommand,
)
from app.organization.domain.entity import Organization
from app.organization.domain.repository import OrganizationRepository
from app.organization.domain.usecase import OrganizationUseCase
from core.db.transactional import transactional


class OrganizationService(OrganizationUseCase):
    def __init__(self, *, repository: OrganizationRepository):
        self.repository = repository

    @transactional
    async def create_organization(
        self,
        command: CreateOrganizationCommand,
    ) -> Organization:
        existing_organization = await self.repository.get_by_code(command.code)
        if existing_organization is not None:
            raise OrganizationCodeAlreadyExistsException()

        organization = Organization(
            code=command.code,
            name=command.name,
            auth_provider=command.auth_provider,
            is_active=command.is_active,
        )
        await self.repository.save(organization)
        return organization

    async def get_organization(self, organization_id: UUID) -> Organization:
        organization = await self.repository.get_by_id(organization_id)
        if organization is None:
            raise OrganizationNotFoundException()
        return organization

    async def list_organizations(self) -> list[Organization]:
        return list(await self.repository.list())

    @transactional
    async def update_organization(
        self,
        organization_id: UUID,
        command: UpdateOrganizationCommand,
    ) -> Organization:
        organization = await self.repository.get_by_id(organization_id)
        if organization is None:
            raise OrganizationNotFoundException()

        delivered_fields = command.model_fields_set

        if (
            "code" in delivered_fields
            and command.code is not None
            and command.code != organization.code
        ):
            existing_organization = await self.repository.get_by_code(
                command.code
            )
            if existing_organization is not None:
                raise OrganizationCodeAlreadyExistsException()
            organization.code = command.code

        if "name" in delivered_fields and command.name is not None:
            organization.name = command.name

        if (
            "auth_provider" in delivered_fields
            and command.auth_provider is not None
        ):
            organization.auth_provider = command.auth_provider

        if "is_active" in delivered_fields and command.is_active is not None:
            organization.is_active = command.is_active

        await self.repository.save(organization)
        return organization

    @transactional
    async def delete_organization(self, organization_id: UUID) -> Organization:
        organization = await self.repository.get_by_id(organization_id)
        if organization is None:
            raise OrganizationNotFoundException()

        organization.delete()
        await self.repository.save(organization)
        return organization
