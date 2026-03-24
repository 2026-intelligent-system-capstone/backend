from uuid import UUID

from dependency_injector.wiring import Provide, inject
from fastapi import APIRouter, Depends

from app.auth.adapter.input.api.v1.deps import require_authenticated_user
from app.auth.domain.entity import CurrentUser
from app.user.adapter.input.api.v1.request import (
    CreateUserRequest,
    UpdateUserRequest,
)
from app.user.adapter.input.api.v1.response import (
    UserListResponse,
    UserPayload,
    UserResponse,
)
from app.user.container import UserContainer
from app.user.domain.command import CreateUserCommand, UpdateUserCommand
from app.user.domain.usecase import UserUseCase

router = APIRouter(prefix="/users", tags=["users"])


@router.post("", response_model=UserResponse)
@inject
async def create_user(
    request: CreateUserRequest,
    usecase: UserUseCase = Depends(Provide[UserContainer.service]),
):
    user = await usecase.create_user(CreateUserCommand(**request.model_dump()))
    return UserResponse(
        data=UserPayload(
            id=str(user.id),
            organization_id=str(user.organization_id),
            login_id=user.login_id,
            role=user.role.value,
            email=user.email,
            name=user.name,
            status=user.status.value,
            is_deleted=user.is_deleted,
        )
    )


@router.get("", response_model=UserListResponse)
@inject
async def list_users(
    current_user: CurrentUser = Depends(require_authenticated_user),
    usecase: UserUseCase = Depends(Provide[UserContainer.service]),
):
    del current_user
    users = await usecase.list_users()
    return UserListResponse(
        data=[
            UserPayload(
                id=str(user.id),
                organization_id=str(user.organization_id),
                login_id=user.login_id,
                role=user.role.value,
                email=user.email,
                name=user.name,
                status=user.status.value,
                is_deleted=user.is_deleted,
            )
            for user in users
        ]
    )


@router.get("/{user_id}", response_model=UserResponse)
@inject
async def get_user(
    user_id: UUID,
    usecase: UserUseCase = Depends(Provide[UserContainer.service]),
):
    user = await usecase.get_user(user_id)
    return UserResponse(
        data=UserPayload(
            id=str(user.id),
            organization_id=str(user.organization_id),
            login_id=user.login_id,
            role=user.role.value,
            email=user.email,
            name=user.name,
            status=user.status.value,
            is_deleted=user.is_deleted,
        )
    )


@router.patch("/{user_id}", response_model=UserResponse)
@inject
async def update_user(
    user_id: UUID,
    request: UpdateUserRequest,
    usecase: UserUseCase = Depends(Provide[UserContainer.service]),
):
    user = await usecase.update_user(
        user_id,
        UpdateUserCommand(**request.model_dump(exclude_unset=True)),
    )
    return UserResponse(
        data=UserPayload(
            id=str(user.id),
            organization_id=str(user.organization_id),
            login_id=user.login_id,
            role=user.role.value,
            email=user.email,
            name=user.name,
            status=user.status.value,
            is_deleted=user.is_deleted,
        )
    )


@router.delete("/{user_id}", response_model=UserResponse)
@inject
async def delete_user(
    user_id: UUID,
    usecase: UserUseCase = Depends(Provide[UserContainer.service]),
):
    user = await usecase.delete_user(user_id)
    return UserResponse(
        data=UserPayload(
            id=str(user.id),
            organization_id=str(user.organization_id),
            login_id=user.login_id,
            role=user.role.value,
            email=user.email,
            name=user.name,
            status=user.status.value,
            is_deleted=user.is_deleted,
        )
    )
