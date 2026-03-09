from dependency_injector.wiring import Provide, inject
from fastapi import APIRouter, Depends

from app.user.application.dto.request import CreateUserRequest
from app.user.application.dto.response import CreateUserResponse, UserResponse
from app.user.application.service.user import UserService
from app.user.container import UserContainer

router = APIRouter(prefix="/users", tags=["users"])


@router.post("", response_model=CreateUserResponse)
@inject
async def create_user(
    request: CreateUserRequest,
    service: UserService = Depends(Provide[UserContainer.service]),
):
    user = await service.create_user(request)
    return CreateUserResponse(
        data=UserResponse(
            id=str(user.id),
            username=user.username,
            email=user.email,
            nickname=user.profile.nickname,
        )
    )
