from pydantic import BaseModel, Field

from core.common.response.base import BaseResponse


class AuthPayload(BaseModel):
    user_id: str | None = None
    organization_id: str | None = None
    organization_code: str | None = None
    role: str | None = None
    authenticated: bool


class AuthResponse(BaseResponse):
    data: AuthPayload = Field(default=...)
