from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from app.user.domain.entity import User, UserRole


@dataclass(frozen=True)
class CurrentUser:
    id: UUID
    organization_id: UUID
    login_id: str
    role: UserRole
    authenticated: bool = True

    @classmethod
    def from_user(cls, user: User) -> CurrentUser:
        return cls(
            id=user.id,
            organization_id=user.organization_id,
            login_id=user.login_id,
            role=user.role,
        )
