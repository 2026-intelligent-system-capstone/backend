from pydantic import Field

from core.common.request.base import BaseRequest


class LoginRequest(BaseRequest):
    organization_code: str = Field(..., min_length=2, max_length=50)
    login_id: str = Field(..., min_length=1, max_length=100)
    password: str = Field(..., min_length=8, max_length=100)
