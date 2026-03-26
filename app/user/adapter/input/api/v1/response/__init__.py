from pydantic import BaseModel, Field

from core.common.response.base import BaseResponse


class UserPayload(BaseModel):
    id: str
    organization_id: str
    login_id: str
    role: str
    email: str | None = None
    name: str
    status: str
    is_deleted: bool


class UserResponse(BaseResponse):
    data: UserPayload = Field(default=...)


class UserListResponse(BaseResponse):
    data: list[UserPayload] = Field(default=...)
