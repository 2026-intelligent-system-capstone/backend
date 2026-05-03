from uuid import UUID, uuid4

import pytest

from app.organization.application.exception import (
    OrganizationCodeAlreadyExistsException,
    OrganizationNotFoundException,
)
from app.organization.application.service import OrganizationService
from app.organization.domain.command import (
    CreateOrganizationCommand,
    UpdateOrganizationCommand,
)
from app.organization.domain.entity import (
    Organization,
    OrganizationAuthProvider,
)
from app.organization.domain.repository import OrganizationRepository

HANSUNG_ID = UUID("11111111-1111-1111-1111-111111111111")


class InMemoryOrganizationRepository(OrganizationRepository):
    def __init__(self, organizations: list[Organization] | None = None):
        self.organizations = {
            organization.id: organization
            for organization in organizations or []
        }

    async def save(self, entity: Organization) -> None:
        self.organizations[entity.id] = entity

    async def get_by_id(self, entity_id: UUID) -> Organization | None:
        return self.organizations.get(entity_id)

    async def get_by_code(self, code: str) -> Organization | None:
        return next(
            (
                organization
                for organization in self.organizations.values()
                if organization.code == code
            ),
            None,
        )

    async def list(self) -> list[Organization]:
        return list(self.organizations.values())


def make_organization() -> Organization:
    organization = Organization(
        code="univ_hansung",
        name="한성대학교",
        auth_provider=OrganizationAuthProvider.HANSUNG_SIS,
    )
    organization.id = HANSUNG_ID
    return organization


@pytest.mark.asyncio
async def test_create_organization_success():
    service = OrganizationService(repository=InMemoryOrganizationRepository())

    organization = await service.create_organization(
        CreateOrganizationCommand(
            code="univ_hansung",
            name="한성대학교",
            auth_provider=OrganizationAuthProvider.HANSUNG_SIS,
        )
    )

    assert organization.code == "univ_hansung"
    assert organization.name == "한성대학교"


@pytest.mark.asyncio
async def test_create_organization_duplicate_code_raises():
    service = OrganizationService(
        repository=InMemoryOrganizationRepository([make_organization()])
    )

    with pytest.raises(OrganizationCodeAlreadyExistsException):
        await service.create_organization(
            CreateOrganizationCommand(
                code="univ_hansung",
                name="다른 조직",
                auth_provider=OrganizationAuthProvider.HANSUNG_SIS,
            )
        )


@pytest.mark.asyncio
async def test_list_organizations_returns_all_organizations():
    service = OrganizationService(
        repository=InMemoryOrganizationRepository([make_organization()])
    )

    organizations = await service.list_organizations()

    assert len(organizations) == 1
    assert organizations[0].code == "univ_hansung"


@pytest.mark.asyncio
async def test_get_organization_returns_organization():
    service = OrganizationService(
        repository=InMemoryOrganizationRepository([make_organization()])
    )

    organization = await service.get_organization(HANSUNG_ID)

    assert organization.name == "한성대학교"


@pytest.mark.asyncio
async def test_get_organization_not_found_raises():
    service = OrganizationService(repository=InMemoryOrganizationRepository())

    with pytest.raises(OrganizationNotFoundException):
        await service.get_organization(uuid4())


@pytest.mark.asyncio
async def test_update_organization_success():
    service = OrganizationService(
        repository=InMemoryOrganizationRepository([make_organization()])
    )

    organization = await service.update_organization(
        HANSUNG_ID,
        UpdateOrganizationCommand(name="한성대학교 테스트", is_active=False),
    )

    assert organization.name == "한성대학교 테스트"
    assert organization.is_active is False


@pytest.mark.asyncio
async def test_update_organization_duplicate_code_raises():
    other_organization = Organization(
        code="univ_other",
        name="다른대학교",
        auth_provider=OrganizationAuthProvider.HANSUNG_SIS,
    )
    other_organization.id = uuid4()
    service = OrganizationService(
        repository=InMemoryOrganizationRepository([
            make_organization(),
            other_organization,
        ])
    )

    with pytest.raises(OrganizationCodeAlreadyExistsException):
        await service.update_organization(
            other_organization.id,
            UpdateOrganizationCommand(code="univ_hansung"),
        )


@pytest.mark.asyncio
async def test_update_organization_not_found_raises():
    service = OrganizationService(repository=InMemoryOrganizationRepository())

    with pytest.raises(OrganizationNotFoundException):
        await service.update_organization(
            uuid4(),
            UpdateOrganizationCommand(name="수정된 조직"),
        )


@pytest.mark.asyncio
async def test_update_organization_changes_code_and_auth_provider():
    service = OrganizationService(
        repository=InMemoryOrganizationRepository([make_organization()])
    )

    organization = await service.update_organization(
        HANSUNG_ID,
        UpdateOrganizationCommand(
            code="univ_hansung_new",
            auth_provider=OrganizationAuthProvider.HANSUNG_SIS,
        ),
    )

    assert organization.code == "univ_hansung_new"
    assert organization.auth_provider == OrganizationAuthProvider.HANSUNG_SIS


@pytest.mark.asyncio
async def test_update_organization_keeps_omitted_fields_unchanged():
    service = OrganizationService(
        repository=InMemoryOrganizationRepository([make_organization()])
    )

    organization = await service.update_organization(
        HANSUNG_ID,
        UpdateOrganizationCommand(name="이름만 변경"),
    )

    assert organization.name == "이름만 변경"
    assert organization.code == "univ_hansung"
    assert organization.is_active is True


@pytest.mark.asyncio
async def test_delete_organization_sets_deleted_state():
    service = OrganizationService(
        repository=InMemoryOrganizationRepository([make_organization()])
    )

    organization = await service.delete_organization(HANSUNG_ID)

    assert organization.is_active is False
    assert organization.is_deleted is True


@pytest.mark.asyncio
async def test_delete_organization_not_found_raises():
    service = OrganizationService(repository=InMemoryOrganizationRepository())

    with pytest.raises(OrganizationNotFoundException):
        await service.delete_organization(uuid4())
