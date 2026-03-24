from dataclasses import dataclass

from app.user.domain.entity import UserRole


@dataclass
class OrganizationIdentity:
    login_id: str
    role: UserRole
    name: str
    email: str | None = None
