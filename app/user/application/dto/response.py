from pydantic import BaseModel, ConfigDict

from core.common.response.base import BaseResponse


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    username: str
    email: str
    nickname: str
    real_name: str
    phone_number: str | None = None
    is_deleted: bool


class UserListResponse(BaseResponse):
    data: list[UserResponse]


class CreateUserResponse(BaseResponse):
    data: UserResponse


class GetUserResponse(BaseResponse):
    data: UserResponse


class UpdateUserResponse(BaseResponse):
    data: UserResponse


class DeleteUserResponse(BaseResponse):
    data: UserResponse
