from abc import ABC, abstractmethod

from fastapi import Depends, Request

from app.auth.application.exception import (
    AuthForbiddenException,
    AuthUnauthorizedException,
)
from app.auth.domain.entity import CurrentUser
from app.user.domain.entity import UserRole, UserStatus
from app.user.domain.repository import UserRepository


def get_user_repository(request: Request) -> UserRepository:
    return request.app.container.user.repository()


async def get_current_user(
    request: Request,
    user_repository: UserRepository = Depends(get_user_repository),
) -> CurrentUser:
    user_id = getattr(request.user, "id", None)
    if user_id is None:
        raise AuthUnauthorizedException()

    user = await user_repository.get_by_id(user_id)
    if user is None or user.status == UserStatus.BLOCKED:
        raise AuthUnauthorizedException()

    current_user = CurrentUser.from_user(user)
    request.state.current_user = current_user
    return current_user


class BasePermission(ABC):
    exception = AuthForbiddenException

    @abstractmethod
    async def has_permission(self, request: Request) -> bool:
        pass


class IsAuthenticated(BasePermission):
    exception = AuthUnauthorizedException

    async def has_permission(self, request: Request) -> bool:
        return getattr(request.user, "id", None) is not None


class IsAdmin(BasePermission):
    async def has_permission(self, request: Request) -> bool:
        current_user = getattr(request.state, "current_user", None)
        if current_user is None:
            return False
        return current_user.role == UserRole.ADMIN


class IsProfessorOrAdmin(BasePermission):
    async def has_permission(self, request: Request) -> bool:
        current_user = getattr(request.state, "current_user", None)
        if current_user is None:
            return False
        return current_user.role in (UserRole.PROFESSOR, UserRole.ADMIN)


class PermissionDependency:
    def __init__(self, permissions: list[type[BasePermission]]):
        self.permissions = permissions

    async def __call__(
        self,
        request: Request,
        _: CurrentUser = Depends(get_current_user),
    ) -> None:
        for permission in self.permissions:
            checker = permission()
            if not await checker.has_permission(request):
                raise checker.exception()
