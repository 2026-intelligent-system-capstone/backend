from collections.abc import Iterable
from uuid import UUID

from app.auth.application.exception import AuthForbiddenException
from app.auth.domain.entity import CurrentUser
from app.classroom.application.exception import (
    ClassroomAlreadyExistsException,
    ClassroomInvalidProfessorRoleException,
    ClassroomInvalidStudentRoleException,
    ClassroomNotFoundException,
    ClassroomProfessorNotFoundException,
    ClassroomStudentAlreadyInvitedException,
    ClassroomStudentNotEnrolledException,
    ClassroomStudentNotFoundException,
)
from app.classroom.domain.command import (
    CreateClassroomCommand,
    InviteClassroomStudentsCommand,
    RemoveClassroomStudentCommand,
    UpdateClassroomCommand,
)
from app.classroom.domain.entity import Classroom
from app.classroom.domain.repository import ClassroomRepository
from app.classroom.domain.usecase import ClassroomUseCase
from app.user.domain.entity import User, UserRole
from app.user.domain.repository import UserRepository
from core.db.transactional import transactional


class ClassroomService(ClassroomUseCase):
    def __init__(
        self,
        *,
        repository: ClassroomRepository,
        user_repository: UserRepository,
    ):
        self.repository = repository
        self.user_repository = user_repository

    @transactional
    async def create_classroom(
        self,
        *,
        current_user: CurrentUser,
        command: CreateClassroomCommand,
    ) -> Classroom:
        self._ensure_professor_or_admin(current_user)

        professor_ids = self._build_professor_ids(
            professor_ids=command.professor_ids,
            current_user=current_user,
        )
        student_ids = _unique_ids(command.student_ids)

        await self._validate_members(
            organization_id=current_user.organization_id,
            professor_ids=professor_ids,
            student_ids=student_ids,
        )

        existing_classroom = (
            await self.repository.get_by_organization_and_name_and_term(
                current_user.organization_id,
                command.name,
                command.grade,
                command.semester,
                command.section,
            )
        )
        if existing_classroom is not None:
            raise ClassroomAlreadyExistsException()

        classroom = Classroom(
            current_user.organization_id,
            name=command.name,
            professor_ids=professor_ids,
            grade=command.grade,
            semester=command.semester,
            section=command.section,
            description=command.description,
            student_ids=student_ids,
            allow_student_material_access=(
                command.allow_student_material_access
            ),
        )
        await self.repository.save(classroom)
        return classroom

    async def get_classroom(
        self,
        *,
        classroom_id: UUID,
        current_user: CurrentUser,
    ) -> Classroom:
        classroom = await self.repository.get_by_id(classroom_id)
        if classroom is None:
            raise ClassroomNotFoundException()

        if not self._can_access_classroom(classroom, current_user):
            raise AuthForbiddenException()

        return classroom

    async def get_manageable_classroom(
        self,
        *,
        classroom_id: UUID,
        current_user: CurrentUser,
    ) -> Classroom:
        self._ensure_professor_or_admin(current_user)

        classroom = await self.get_classroom(
            classroom_id=classroom_id,
            current_user=current_user,
        )
        self._ensure_classroom_manager(classroom, current_user)
        return classroom

    async def list_classrooms(
        self,
        *,
        current_user: CurrentUser,
    ) -> list[Classroom]:
        classrooms = await self.repository.list_by_organization(
            current_user.organization_id
        )
        return [
            classroom
            for classroom in classrooms
            if self._can_access_classroom(classroom, current_user)
        ]

    @transactional
    async def update_classroom(
        self,
        *,
        classroom_id: UUID,
        current_user: CurrentUser,
        command: UpdateClassroomCommand,
    ) -> Classroom:
        classroom = await self.get_manageable_classroom(
            classroom_id=classroom_id,
            current_user=current_user,
        )
        delivered_fields = command.model_fields_set

        name = classroom.name
        if "name" in delivered_fields and command.name is not None:
            name = command.name

        grade = classroom.grade
        if "grade" in delivered_fields and command.grade is not None:
            grade = command.grade

        semester = classroom.semester
        if "semester" in delivered_fields and command.semester is not None:
            semester = command.semester

        section = classroom.section
        if "section" in delivered_fields and command.section is not None:
            section = command.section

        if (
            name != classroom.name
            or grade != classroom.grade
            or semester != classroom.semester
            or section != classroom.section
        ):
            existing_classroom = (
                await self.repository.get_by_organization_and_name_and_term(
                    classroom.organization_id,
                    name,
                    grade,
                    semester,
                    section,
                )
            )
            if (
                existing_classroom is not None
                and existing_classroom.id != classroom.id
            ):
                raise ClassroomAlreadyExistsException()

        professor_ids = classroom.professor_ids
        if (
            "professor_ids" in delivered_fields
            and command.professor_ids is not None
        ):
            professor_ids = self._build_professor_ids(
                professor_ids=command.professor_ids,
                current_user=current_user,
            )

        student_ids = classroom.student_ids
        if (
            "student_ids" in delivered_fields
            and command.student_ids is not None
        ):
            student_ids = _unique_ids(command.student_ids)

        await self._validate_members(
            organization_id=classroom.organization_id,
            professor_ids=professor_ids,
            student_ids=student_ids,
        )

        classroom.name = name
        classroom.grade = grade
        classroom.semester = semester
        classroom.section = section
        if "description" in delivered_fields:
            classroom.description = command.description
        if (
            "allow_student_material_access" in delivered_fields
            and command.allow_student_material_access is not None
        ):
            classroom.allow_student_material_access = (
                command.allow_student_material_access
            )
        classroom.professor_ids = professor_ids
        classroom.student_ids = student_ids

        await self.repository.save(classroom)
        return classroom

    @transactional
    async def delete_classroom(
        self,
        *,
        classroom_id: UUID,
        current_user: CurrentUser,
    ) -> Classroom:
        classroom = await self.get_manageable_classroom(
            classroom_id=classroom_id,
            current_user=current_user,
        )
        await self.repository.delete(classroom)
        return classroom

    @transactional
    async def invite_classroom_students(
        self,
        *,
        classroom_id: UUID,
        current_user: CurrentUser,
        command: InviteClassroomStudentsCommand,
    ) -> Classroom:
        classroom = await self.get_manageable_classroom(
            classroom_id=classroom_id,
            current_user=current_user,
        )

        invited_student_ids = _unique_ids(command.student_ids)
        duplicate_ids = [
            user_id
            for user_id in invited_student_ids
            if user_id in classroom.student_ids
        ]
        if duplicate_ids:
            raise ClassroomStudentAlreadyInvitedException(
                detail={
                    "student_ids": [str(user_id) for user_id in duplicate_ids]
                }
            )

        updated_student_ids = classroom.student_ids + invited_student_ids
        await self._validate_students_for_classroom(
            organization_id=classroom.organization_id,
            student_ids=updated_student_ids,
        )
        classroom.student_ids = _unique_ids(updated_student_ids)
        await self.repository.save(classroom)
        return classroom

    @transactional
    async def remove_classroom_student(
        self,
        *,
        classroom_id: UUID,
        current_user: CurrentUser,
        command: RemoveClassroomStudentCommand,
    ) -> Classroom:
        classroom = await self.get_manageable_classroom(
            classroom_id=classroom_id,
            current_user=current_user,
        )

        if command.student_id not in classroom.student_ids:
            raise ClassroomStudentNotEnrolledException(
                detail={"student_id": str(command.student_id)}
            )

        classroom.student_ids = [
            user_id
            for user_id in classroom.student_ids
            if user_id != command.student_id
        ]
        await self.repository.save(classroom)
        return classroom

    async def _validate_members(
        self,
        *,
        organization_id: UUID,
        professor_ids: list[UUID],
        student_ids: list[UUID],
    ) -> None:
        users_by_id = await self._get_organization_users(organization_id)

        self._validate_professors(users_by_id, professor_ids)
        self._validate_students(users_by_id, student_ids)

    async def _validate_students_for_classroom(
        self,
        *,
        organization_id: UUID,
        student_ids: list[UUID],
    ) -> None:
        users_by_id = await self._get_organization_users(organization_id)
        self._validate_students(users_by_id, student_ids)

    async def _get_organization_users(
        self,
        organization_id: UUID,
    ) -> dict[UUID, User]:
        users = await self.user_repository.list_by_organization(organization_id)
        return {user.id: user for user in users if not user.is_deleted}

    @staticmethod
    def _validate_professors(
        users_by_id: dict[UUID, User],
        professor_ids: list[UUID],
    ) -> None:
        missing_ids = [
            user_id for user_id in professor_ids if user_id not in users_by_id
        ]
        if missing_ids:
            raise ClassroomProfessorNotFoundException(
                detail={
                    "professor_ids": [str(user_id) for user_id in missing_ids]
                }
            )

        invalid_ids = [
            user_id
            for user_id in professor_ids
            if users_by_id[user_id].role != UserRole.PROFESSOR
        ]
        if invalid_ids:
            raise ClassroomInvalidProfessorRoleException(
                detail={
                    "professor_ids": [str(user_id) for user_id in invalid_ids]
                }
            )

    @staticmethod
    def _validate_students(
        users_by_id: dict[UUID, User],
        student_ids: list[UUID],
    ) -> None:
        missing_ids = [
            user_id for user_id in student_ids if user_id not in users_by_id
        ]
        if missing_ids:
            raise ClassroomStudentNotFoundException(
                detail={
                    "student_ids": [str(user_id) for user_id in missing_ids]
                }
            )

        invalid_ids = [
            user_id
            for user_id in student_ids
            if users_by_id[user_id].role != UserRole.STUDENT
        ]
        if invalid_ids:
            raise ClassroomInvalidStudentRoleException(
                detail={
                    "student_ids": [str(user_id) for user_id in invalid_ids]
                }
            )

    @staticmethod
    def _ensure_professor_or_admin(current_user: CurrentUser) -> None:
        if current_user.role not in (UserRole.PROFESSOR, UserRole.ADMIN):
            raise AuthForbiddenException()

    @staticmethod
    def _ensure_classroom_manager(
        classroom: Classroom,
        current_user: CurrentUser,
    ) -> None:
        if current_user.role == UserRole.ADMIN:
            return

        if current_user.id in classroom.professor_ids:
            return

        raise AuthForbiddenException()

    @staticmethod
    def _can_access_classroom(
        classroom: Classroom,
        current_user: CurrentUser,
    ) -> bool:
        if classroom.organization_id != current_user.organization_id:
            return False

        if current_user.role == UserRole.ADMIN:
            return True

        if current_user.role == UserRole.PROFESSOR:
            return current_user.id in classroom.professor_ids

        return current_user.id in classroom.student_ids

    @staticmethod
    def _build_professor_ids(
        *,
        professor_ids: Iterable[UUID],
        current_user: CurrentUser,
    ) -> list[UUID]:
        normalized_professor_ids = _unique_ids(professor_ids)
        if (
            current_user.role == UserRole.PROFESSOR
            and current_user.id not in normalized_professor_ids
        ):
            normalized_professor_ids.append(current_user.id)

        return normalized_professor_ids


def _unique_ids(user_ids: Iterable[UUID]) -> list[UUID]:
    return list(dict.fromkeys(user_ids))
