from pydantic import EmailStr, Field

from core.common.request.base import BaseRequest


class LoginRequest(BaseRequest):
    email: EmailStr = Field(...)
    password: str = Field(..., min_length=8, max_length=100)
