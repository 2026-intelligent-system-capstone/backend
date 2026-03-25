from abc import ABC, abstractmethod
from uuid import UUID

from app.auth.domain.entity import CurrentUser
from app.classroom_material.application.dto import ClassroomMaterialResult
from app.classroom_material.domain.command import (
    CreateClassroomMaterialCommand,
    UpdateClassroomMaterialCommand,
)
from app.file.domain.service import FileUploadData


class ClassroomMaterialUseCase(ABC):
    @abstractmethod
    async def create_classroom_material(
        self,
        *,
        classroom_id: UUID,
        current_user: CurrentUser,
        command: CreateClassroomMaterialCommand,
        file_upload: FileUploadData,
    ) -> ClassroomMaterialResult:
        """Create classroom material."""

    @abstractmethod
    async def list_classroom_materials(
        self,
        *,
        classroom_id: UUID,
        current_user: CurrentUser,
    ) -> list[ClassroomMaterialResult]:
        """List classroom materials."""

    @abstractmethod
    async def get_classroom_material(
        self,
        *,
        classroom_id: UUID,
        material_id: UUID,
        current_user: CurrentUser,
    ) -> ClassroomMaterialResult:
        """Get classroom material."""

    @abstractmethod
    async def update_classroom_material(
        self,
        *,
        classroom_id: UUID,
        material_id: UUID,
        current_user: CurrentUser,
        command: UpdateClassroomMaterialCommand,
        file_upload: FileUploadData | None = None,
    ) -> ClassroomMaterialResult:
        """Update classroom material."""

    @abstractmethod
    async def delete_classroom_material(
        self,
        *,
        classroom_id: UUID,
        material_id: UUID,
        current_user: CurrentUser,
    ) -> ClassroomMaterialResult:
        """Delete classroom material."""
