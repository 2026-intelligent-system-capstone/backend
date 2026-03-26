from pydantic import Field, model_validator

from app.organization.domain.entity import OrganizationAuthProvider
from core.common.request.base import BaseRequest


class CreateOrganizationRequest(BaseRequest):
    code: str = Field(..., min_length=2, max_length=50)
    name: str = Field(..., min_length=2, max_length=100)
    auth_provider: OrganizationAuthProvider = Field(...)
    is_active: bool = Field(True)


class UpdateOrganizationRequest(BaseRequest):
    code: str | None = Field(None, min_length=2, max_length=50)
    name: str | None = Field(None, min_length=2, max_length=100)
    auth_provider: OrganizationAuthProvider | None = Field(None)
    is_active: bool | None = Field(None)

    @model_validator(mode="after")
    def validate_non_empty_update(self):
        if not self.model_fields_set:
            raise ValueError("최소 하나 이상의 수정 필드가 필요합니다.")
        return self
