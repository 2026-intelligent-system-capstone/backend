from pydantic import BaseModel, ConfigDict

from core.common.response.base import BaseResponse


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    username: str
    email: str
    nickname: str


class CreateUserResponse(BaseResponse):
    data: UserResponse
