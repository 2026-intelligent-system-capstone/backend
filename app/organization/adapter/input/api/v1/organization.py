from uuid import UUID

from dependency_injector.wiring import Provide, inject
from fastapi import APIRouter, Depends

from app.organization.adapter.input.api.v1.request import (
    CreateOrganizationRequest,
    UpdateOrganizationRequest,
)
from app.organization.adapter.input.api.v1.response import (
    OrganizationListResponse,
    OrganizationPayload,
    OrganizationResponse,
)
from app.organization.container import OrganizationContainer
from app.organization.domain.command import (
    CreateOrganizationCommand,
    UpdateOrganizationCommand,
)
from app.organization.domain.usecase import OrganizationUseCase
from core.fastapi.dependencies import IsAdmin, PermissionDependency

router = APIRouter(prefix="/organizations", tags=["organizations"])


@router.post(
    "",
    response_model=OrganizationResponse,
    dependencies=[Depends(PermissionDependency([IsAdmin]))],
)
@inject
async def create_organization(
    request: CreateOrganizationRequest,
    usecase: OrganizationUseCase = Depends(
        Provide[OrganizationContainer.service]
    ),
):
    organization = await usecase.create_organization(
        CreateOrganizationCommand(**request.model_dump())
    )
    return OrganizationResponse(
        data=OrganizationPayload(
            id=str(organization.id),
            code=organization.code,
            name=organization.name,
            auth_provider=organization.auth_provider.value,
            is_active=organization.is_active,
        )
    )


@router.get("", response_model=OrganizationListResponse)
@inject
async def list_organizations(
    usecase: OrganizationUseCase = Depends(
        Provide[OrganizationContainer.service]
    ),
):
    organizations = await usecase.list_organizations()
    return OrganizationListResponse(
        data=[
            OrganizationPayload(
                id=str(organization.id),
                code=organization.code,
                name=organization.name,
                auth_provider=organization.auth_provider.value,
                is_active=organization.is_active,
            )
            for organization in organizations
        ]
    )


@router.get("/{organization_id}", response_model=OrganizationResponse)
@inject
async def get_organization(
    organization_id: UUID,
    usecase: OrganizationUseCase = Depends(
        Provide[OrganizationContainer.service]
    ),
):
    organization = await usecase.get_organization(organization_id)
    return OrganizationResponse(
        data=OrganizationPayload(
            id=str(organization.id),
            code=organization.code,
            name=organization.name,
            auth_provider=organization.auth_provider.value,
            is_active=organization.is_active,
        )
    )


@router.patch(
    "/{organization_id}",
    response_model=OrganizationResponse,
    dependencies=[Depends(PermissionDependency([IsAdmin]))],
)
@inject
async def update_organization(
    organization_id: UUID,
    request: UpdateOrganizationRequest,
    usecase: OrganizationUseCase = Depends(
        Provide[OrganizationContainer.service]
    ),
):
    organization = await usecase.update_organization(
        organization_id,
        UpdateOrganizationCommand(**request.model_dump(exclude_unset=True)),
    )
    return OrganizationResponse(
        data=OrganizationPayload(
            id=str(organization.id),
            code=organization.code,
            name=organization.name,
            auth_provider=organization.auth_provider.value,
            is_active=organization.is_active,
        )
    )


@router.delete(
    "/{organization_id}",
    response_model=OrganizationResponse,
    dependencies=[Depends(PermissionDependency([IsAdmin]))],
)
@inject
async def delete_organization(
    organization_id: UUID,
    usecase: OrganizationUseCase = Depends(
        Provide[OrganizationContainer.service]
    ),
):
    organization = await usecase.delete_organization(organization_id)
    return OrganizationResponse(
        data=OrganizationPayload(
            id=str(organization.id),
            code=organization.code,
            name=organization.name,
            auth_provider=organization.auth_provider.value,
            is_active=organization.is_active,
        )
    )
