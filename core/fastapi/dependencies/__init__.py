from core.fastapi.dependencies.permission import (
    BasePermission,
    IsAdmin,
    IsAuthenticated,
    IsProfessorOrAdmin,
    PermissionDependency,
    get_current_user,
)

__all__ = [
    "BasePermission",
    "IsAdmin",
    "IsAuthenticated",
    "IsProfessorOrAdmin",
    "PermissionDependency",
    "get_current_user",
]
