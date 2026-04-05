from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from uuid import UUID

from core.common.entity import Entity
from core.common.value_object import ValueObject


class UserStatus(ValueObject, StrEnum):
    ACTIVE = "active"
    PENDING = "pending"
    BLOCKED = "blocked"


class UserRole(ValueObject, StrEnum):
    STUDENT = "student"
    PROFESSOR = "professor"
    ADMIN = "admin"


@dataclass
class User(Entity):
    organization_id: UUID
    login_id: str
    role: UserRole
    email: str | None
    name: str
    status: UserStatus = UserStatus.ACTIVE
    is_deleted: bool = False

    @classmethod
    def register(
        cls,
        *,
        organization_id: UUID,
        login_id: str,
        role: UserRole,
        email: str | None,
        name: str,
    ) -> User:
        return cls(
            organization_id=organization_id,
            login_id=login_id,
            role=role,
            email=email,
            name=name,
        )

    @property
    def can_login(self) -> bool:
        return not self.is_deleted and self.status != UserStatus.BLOCKED

    def sync_profile(
        self,
        *,
        login_id: str,
        role: UserRole,
        email: str | None,
        name: str,
    ) -> None:
        self.login_id = login_id
        self.role = role
        self.email = email
        self.name = name

    def update(
        self,
        *,
        login_id: str | None = None,
        role: UserRole | None = None,
        email: str | None = None,
        clear_email: bool = False,
        name: str | None = None,
        status: UserStatus | None = None,
    ) -> None:
        if login_id is not None:
            self.login_id = login_id
        if role is not None:
            self.role = role
        if clear_email:
            self.email = None
        elif email is not None:
            self.email = email
        if name is not None:
            self.name = name
        if status is not None:
            self.status = status

    def delete(self) -> None:
        self.is_deleted = True
