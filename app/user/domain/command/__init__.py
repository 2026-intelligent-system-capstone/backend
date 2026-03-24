from uuid import UUID

from pydantic import BaseModel

from app.user.domain.entity.user import UserRole, UserStatus


class CreateUserCommand(BaseModel):
    organization_id: UUID
    login_id: str
    role: UserRole
    email: str | None = None
    nickname: str
    name: str
    phone_number: str | None = None


class UpdateUserCommand(BaseModel):
    login_id: str | None = None
    role: UserRole | None = None
    email: str | None = None
    nickname: str | None = None
    name: str | None = None
    phone_number: str | None = None
    status: UserStatus | None = None
