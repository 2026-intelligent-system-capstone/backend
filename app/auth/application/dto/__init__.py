from pydantic import BaseModel


class AuthTokensDTO(BaseModel):
    user_id: str
    organization_id: str
    organization_code: str
    role: str
    access_token: str
    refresh_token: str
