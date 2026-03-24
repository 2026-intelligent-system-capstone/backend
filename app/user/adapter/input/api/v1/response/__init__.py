from pydantic import BaseModel, Field

from core.common.response.base import BaseResponse


class UserPayload(BaseModel):
    id: str
    username: str
    email: str
    nickname: str
    real_name: str
    phone_number: str | None = None
    is_deleted: bool


class UserResponse(BaseResponse):
    data: UserPayload = Field(...)


class UserListResponse(BaseResponse):
    data: list[UserPayload] = Field(...)
