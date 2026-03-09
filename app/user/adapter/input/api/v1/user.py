from uuid import UUID

from dependency_injector.wiring import Provide, inject
from fastapi import APIRouter, Depends

from app.user.application.dto.request import CreateUserRequest, UpdateUserRequest
from app.user.application.dto.response import (
    CreateUserResponse,
    DeleteUserResponse,
    GetUserResponse,
    UpdateUserResponse,
    UserListResponse,
    UserResponse,
)
from app.user.application.service.user import UserService
from app.user.container import UserContainer

router = APIRouter(prefix="/users", tags=["users"])


def to_user_response(user) -> UserResponse:
    return UserResponse(
        id=str(user.id),
        username=user.username,
        email=user.email,
        nickname=user.profile.nickname,
        real_name=user.profile.real_name,
        phone_number=user.profile.phone_number,
        is_deleted=user.is_deleted,
    )


@router.post("", response_model=CreateUserResponse)
@inject
async def create_user(
    request: CreateUserRequest,
    service: UserService = Depends(Provide[UserContainer.service]),
):
    user = await service.create_user(request)
    return CreateUserResponse(data=to_user_response(user))


@router.get("", response_model=UserListResponse)
@inject
async def list_users(service: UserService = Depends(Provide[UserContainer.service])):
    users = await service.list_users()
    return UserListResponse(data=[to_user_response(user) for user in users])


@router.get("/{user_id}", response_model=GetUserResponse)
@inject
async def get_user(
    user_id: UUID,
    service: UserService = Depends(Provide[UserContainer.service]),
):
    user = await service.get_user(user_id)
    return GetUserResponse(data=to_user_response(user))


@router.patch("/{user_id}", response_model=UpdateUserResponse)
@inject
async def update_user(
    user_id: UUID,
    request: UpdateUserRequest,
    service: UserService = Depends(Provide[UserContainer.service]),
):
    user = await service.update_user(user_id, request)
    return UpdateUserResponse(data=to_user_response(user))


@router.delete("/{user_id}", response_model=DeleteUserResponse)
@inject
async def delete_user(
    user_id: UUID,
    service: UserService = Depends(Provide[UserContainer.service]),
):
    user = await service.delete_user(user_id)
    return DeleteUserResponse(data=to_user_response(user))
