from uuid import UUID

from pydantic import EmailStr, Field, model_validator

from app.user.domain.entity.user import UserRole, UserStatus
from core.common.request.base import BaseRequest


class CreateUserRequest(BaseRequest):
    organization_id: UUID = Field(...)
    login_id: str = Field(..., min_length=1, max_length=100)
    role: UserRole = Field(...)
    email: EmailStr | None = Field(None)
    nickname: str = Field(..., min_length=2, max_length=100)
    name: str = Field(..., min_length=2, max_length=100)
    phone_number: str | None = Field(None, pattern=r"^\d{2,3}-\d{3,4}-\d{4}$")


class UpdateUserRequest(BaseRequest):
    null_fields = {"phone_number", "email"}

    login_id: str | None = Field(None, min_length=1, max_length=100)
    role: UserRole | None = Field(None)
    email: EmailStr | None = Field(None)
    nickname: str | None = Field(None, min_length=2, max_length=100)
    name: str | None = Field(None, min_length=2, max_length=100)
    phone_number: str | None = Field(None, pattern=r"^\d{2,3}-\d{3,4}-\d{4}$")
    status: UserStatus | None = Field(None)

    @model_validator(mode="after")
    def validate_non_empty_update(self):
        if not self.model_fields_set:
            raise ValueError("최소 하나 이상의 수정 필드가 필요합니다.")
        return self
