from dataclasses import dataclass

from app.user.domain.entity.user import UserRole


@dataclass
class AuthenticatedIdentity:
    login_id: str
    role: UserRole
    name: str
    email: str | None = None
