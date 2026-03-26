from pydantic import BaseModel


class LoginCommand(BaseModel):
    organization_code: str
    login_id: str
    password: str


class RefreshTokenCommand(BaseModel):
    refresh_token: str | None = None


class LogoutCommand(BaseModel):
    refresh_token: str | None = None
