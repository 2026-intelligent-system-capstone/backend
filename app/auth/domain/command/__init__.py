from pydantic import BaseModel, EmailStr


class LoginCommand(BaseModel):
    email: EmailStr
    password: str


class RefreshTokenCommand(BaseModel):
    refresh_token: str | None = None


class LogoutCommand(BaseModel):
    refresh_token: str | None = None
