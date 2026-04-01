from collections.abc import Iterable
from dataclasses import dataclass, field
from uuid import UUID

from app.auth.domain.entity import CurrentUser
from app.classroom.application.exception import (
    ClassroomInvalidProfessorRoleException,
    ClassroomInvalidStudentRoleException,
    ClassroomProfessorNotFoundException,
    ClassroomStudentNotFoundException,
)
from app.user.domain.entity import User, UserRole
from core.common.entity import Entity


@dataclass
class Classroom(Entity):
    organization_id: UUID
    name: str
    professor_ids: list[UUID] = field(default_factory=list)
    grade: int = 1
    semester: str = "1"
    section: str = "01"
    description: str | None = None
    student_ids: list[UUID] = field(default_factory=list)
    allow_student_material_access: bool = False

    @classmethod
    def create(
        cls,
        *,
        organization_id: UUID,
        name: str,
        professor_ids: Iterable[UUID],
        current_user: CurrentUser,
        grade: int,
        semester: str,
        section: str,
        description: str | None,
        student_ids: Iterable[UUID],
        allow_student_material_access: bool,
    ) -> "Classroom":
        classroom = cls(
            organization_id=organization_id,
            name=name,
            grade=grade,
            semester=semester,
            section=section,
            description=description,
            allow_student_material_access=allow_student_material_access,
        )
        classroom.professor_ids = classroom.merge_professor_ids(
            professor_ids,
            current_user=current_user,
        )
        classroom.student_ids = list(dict.fromkeys(student_ids))
        return classroom

    def can_be_accessed_by(self, current_user: CurrentUser) -> bool:
        if self.organization_id != current_user.organization_id:
            return False

        if current_user.role == UserRole.ADMIN:
            return True

        if current_user.role == UserRole.PROFESSOR:
            return current_user.id in self.professor_ids

        return current_user.id in self.student_ids

    def can_be_managed_by(self, current_user: CurrentUser) -> bool:
        return current_user.role == UserRole.ADMIN or (
            current_user.role == UserRole.PROFESSOR
            and current_user.id in self.professor_ids
        )

    def allows_material_access_to(self, current_user: CurrentUser) -> bool:
        return current_user.role != UserRole.STUDENT or (
            self.allow_student_material_access
        )

    def merge_professor_ids(
        self,
        professor_ids: Iterable[UUID],
        *,
        current_user: CurrentUser,
    ) -> list[UUID]:
        normalized_professor_ids = list(dict.fromkeys(professor_ids))
        if (
            current_user.role == UserRole.PROFESSOR
            and current_user.id not in normalized_professor_ids
        ):
            normalized_professor_ids.append(current_user.id)
        return normalized_professor_ids

    def normalized_student_ids(
        self, student_ids: Iterable[UUID]
    ) -> list[UUID]:
        return list(dict.fromkeys(student_ids))

    def update_details(
        self,
        *,
        name: str,
        grade: int,
        semester: str,
        section: str,
        description: str | None,
        replace_description: bool,
        allow_student_material_access: bool | None,
        replace_allow_student_material_access: bool,
        professor_ids: list[UUID],
        student_ids: Iterable[UUID],
    ) -> None:
        self.name = name
        self.grade = grade
        self.semester = semester
        self.section = section
        if replace_description:
            self.description = description
        if replace_allow_student_material_access:
            self.allow_student_material_access = allow_student_material_access
        self.professor_ids = professor_ids
        self.student_ids = list(dict.fromkeys(student_ids))

    def find_duplicate_student_ids(
        self, student_ids: Iterable[UUID]
    ) -> list[UUID]:
        invited_student_ids = list(dict.fromkeys(student_ids))
        return [
            user_id
            for user_id in invited_student_ids
            if user_id in self.student_ids
        ]

    def invited_student_ids(self, student_ids: Iterable[UUID]) -> list[UUID]:
        return self.student_ids + list(dict.fromkeys(student_ids))

    def invite_students(self, student_ids: Iterable[UUID]) -> None:
        self.student_ids = self.invited_student_ids(student_ids)

    def remove_student(self, student_id: UUID) -> bool:
        if student_id not in self.student_ids:
            return False

        self.student_ids = [
            user_id for user_id in self.student_ids if user_id != student_id
        ]
        return True

    def validate_members(self, users_by_id: dict[UUID, User]) -> None:
        self._validate_professors(users_by_id)
        self._validate_students(users_by_id)

    def validate_students(self, users_by_id: dict[UUID, User]) -> None:
        self._validate_students(users_by_id)

    def _validate_professors(self, users_by_id: dict[UUID, User]) -> None:
        missing_ids = [
            user_id for user_id in self.professor_ids if user_id not in users_by_id
        ]
        if missing_ids:
            raise ClassroomProfessorNotFoundException(
                detail={
                    "professor_ids": [str(user_id) for user_id in missing_ids]
                }
            )

        invalid_ids = [
            user_id
            for user_id in self.professor_ids
            if users_by_id[user_id].role != UserRole.PROFESSOR
        ]
        if invalid_ids:
            raise ClassroomInvalidProfessorRoleException(
                detail={
                    "professor_ids": [str(user_id) for user_id in invalid_ids]
                }
            )

    def _validate_students(self, users_by_id: dict[UUID, User]) -> None:
        missing_ids = [
            user_id for user_id in self.student_ids if user_id not in users_by_id
        ]
        if missing_ids:
            raise ClassroomStudentNotFoundException(
                detail={
                    "student_ids": [str(user_id) for user_id in missing_ids]
                }
            )

        invalid_ids = [
            user_id
            for user_id in self.student_ids
            if users_by_id[user_id].role != UserRole.STUDENT
        ]
        if invalid_ids:
            raise ClassroomInvalidStudentRoleException(
                detail={
                    "student_ids": [str(user_id) for user_id in invalid_ids]
                }
            )
