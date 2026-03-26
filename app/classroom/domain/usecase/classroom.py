from abc import ABC, abstractmethod
from uuid import UUID

from app.auth.domain.entity import CurrentUser
from app.classroom.domain.command import (
    CreateClassroomCommand,
    InviteClassroomStudentsCommand,
    RemoveClassroomStudentCommand,
    UpdateClassroomCommand,
)
from app.classroom.domain.entity import Classroom


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
