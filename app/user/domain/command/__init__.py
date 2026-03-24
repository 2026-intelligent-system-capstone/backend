from pydantic import BaseModel


class CreateUserCommand(BaseModel):
    username: str
    password: str
    email: str
    nickname: str
    real_name: str
    phone_number: str | None = None


class UpdateUserCommand(BaseModel):
    username: str | None = None
    password: str | None = None
    email: str | None = None
    nickname: str | None = None
    real_name: str | None = None
    phone_number: str | None = None
