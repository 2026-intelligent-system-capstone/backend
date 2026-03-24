from pydantic import BaseModel


class AuthTokensDTO(BaseModel):
    user_id: str
    access_token: str
    refresh_token: str
