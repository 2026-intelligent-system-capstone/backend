from pydantic import BaseModel, Field

from core.common.response.base import BaseResponse


class OrganizationPayload(BaseModel):
    id: str
    code: str
    name: str
    auth_provider: str
    is_active: bool


class OrganizationResponse(BaseResponse):
    data: OrganizationPayload = Field(default=...)


class OrganizationListResponse(BaseResponse):
    data: list[OrganizationPayload] = Field(default=...)
