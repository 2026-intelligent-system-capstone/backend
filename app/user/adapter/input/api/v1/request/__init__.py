from pydantic import EmailStr, Field, model_validator

from core.common.request.base import BaseRequest


class CreateUserRequest(BaseRequest):
    username: str = Field(..., min_length=4, max_length=50)
    password: str = Field(..., min_length=8, max_length=100)
    email: EmailStr = Field(...)
    nickname: str = Field(..., min_length=2, max_length=100)
    real_name: str = Field(..., min_length=2, max_length=100)
    phone_number: str | None = Field(None, pattern=r"^\d{2,3}-\d{3,4}-\d{4}$")


class UpdateUserRequest(BaseRequest):
    null_fields = {"phone_number"}

    username: str | None = Field(None, min_length=4, max_length=50)
    password: str | None = Field(None, min_length=8, max_length=100)
    email: EmailStr | None = Field(None)
    nickname: str | None = Field(None, min_length=2, max_length=100)
    real_name: str | None = Field(None, min_length=2, max_length=100)
    phone_number: str | None = Field(None, pattern=r"^\d{2,3}-\d{3,4}-\d{4}$")

    @model_validator(mode="after")
    def validate_non_empty_update(self):
        if not any(value is not None for value in self.model_dump().values()):
            raise ValueError("최소 하나 이상의 수정 필드가 필요합니다.")
        return self
