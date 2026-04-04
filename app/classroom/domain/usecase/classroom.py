from abc import ABC, abstractmethod
from uuid import UUID

from app.auth.domain.entity import CurrentUser
from app.classroom.domain.command import (
    CreateClassroomCommand,
    CreateClassroomMaterialCommand,
    InviteClassroomStudentsCommand,
    RemoveClassroomStudentCommand,
    UpdateClassroomCommand,
    UpdateClassroomMaterialCommand,
)
from app.classroom.domain.entity import Classroom, ClassroomMaterialDetail
from app.file.domain.entity.file_download import FileDownload
from app.file.domain.service import FileUploadData


class ClassroomUseCase(ABC):
    @abstractmethod
    async def create_classroom(
        self,
        *,
        current_user: CurrentUser,
        command: CreateClassroomCommand,
    ) -> Classroom:
        """Create classroom."""

    @abstractmethod
    async def get_classroom(
        self,
        *,
        classroom_id: UUID,
        current_user: CurrentUser,
    ) -> Classroom:
        """Get classroom."""

    @abstractmethod
    async def get_manageable_classroom(
        self,
        *,
        classroom_id: UUID,
        current_user: CurrentUser,
    ) -> Classroom:
        """Get classroom current actor can manage."""

    @abstractmethod
    async def list_classrooms(
        self,
        *,
        current_user: CurrentUser,
    ) -> list[Classroom]:
        """List classrooms for organization."""

    @abstractmethod
    async def update_classroom(
        self,
        *,
        classroom_id: UUID,
        current_user: CurrentUser,
        command: UpdateClassroomCommand,
    ) -> Classroom:
        """Update classroom."""

    @abstractmethod
    async def delete_classroom(
        self,
        *,
        classroom_id: UUID,
        current_user: CurrentUser,
    ) -> Classroom:
        """Delete classroom."""

    @abstractmethod
    async def invite_classroom_students(
        self,
        *,
        classroom_id: UUID,
        current_user: CurrentUser,
        command: InviteClassroomStudentsCommand,
    ) -> Classroom:
        """Invite students to classroom."""

    @abstractmethod
    async def remove_classroom_student(
        self,
        *,
        classroom_id: UUID,
        current_user: CurrentUser,
        command: RemoveClassroomStudentCommand,
    ) -> Classroom:
        """Remove student from classroom."""

    @abstractmethod
    async def create_classroom_material(
        self,
        *,
        classroom_id: UUID,
        current_user: CurrentUser,
        command: CreateClassroomMaterialCommand,
        file_upload: FileUploadData,
    ) -> ClassroomMaterialDetail:
        """Create classroom material."""

    @abstractmethod
    async def list_classroom_materials(
        self,
        *,
        classroom_id: UUID,
        current_user: CurrentUser,
    ) -> list[ClassroomMaterialDetail]:
        """List classroom materials."""

    @abstractmethod
    async def get_classroom_material(
        self,
        *,
        classroom_id: UUID,
        material_id: UUID,
        current_user: CurrentUser,
    ) -> ClassroomMaterialDetail:
        """Get classroom material."""

    @abstractmethod
    async def get_classroom_material_download(
        self,
        *,
        classroom_id: UUID,
        material_id: UUID,
        current_user: CurrentUser,
    ) -> FileDownload:
        """Get classroom material download content."""

    @abstractmethod
    async def update_classroom_material(
        self,
        *,
        classroom_id: UUID,
        material_id: UUID,
        current_user: CurrentUser,
        command: UpdateClassroomMaterialCommand,
        file_upload: FileUploadData | None = None,
    ) -> ClassroomMaterialDetail:
        """Update classroom material."""

    @abstractmethod
    async def reingest_classroom_material(
        self,
        *,
        classroom_id: UUID,
        material_id: UUID,
        current_user: CurrentUser,
    ) -> ClassroomMaterialDetail:
        """Re-ingest classroom material."""

    @abstractmethod
    async def delete_classroom_material(
        self,
        *,
        classroom_id: UUID,
        material_id: UUID,
        current_user: CurrentUser,
    ) -> ClassroomMaterialDetail:
        """Delete classroom material."""
