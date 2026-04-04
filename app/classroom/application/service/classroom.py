from uuid import UUID

from app.auth.application.exception import AuthForbiddenException
from app.auth.domain.entity import CurrentUser
from app.classroom.application.exception import (
    ClassroomAlreadyExistsException,
    ClassroomMaterialNotFoundException,
    ClassroomNotFoundException,
    ClassroomStudentAlreadyInvitedException,
    ClassroomStudentNotEnrolledException,
)
from app.classroom.domain.command import (
    CreateClassroomCommand,
    CreateClassroomMaterialCommand,
    InviteClassroomStudentsCommand,
    RemoveClassroomStudentCommand,
    UpdateClassroomCommand,
    UpdateClassroomMaterialCommand,
)
from app.classroom.domain.entity import (
    Classroom,
    ClassroomMaterial,
    ClassroomMaterialDetail,
)
from app.classroom.domain.exception import (
    ClassroomMaterialIngestDomainException,
    ClassroomMaterialIngestEmptyScopeDomainException,
)
from app.classroom.domain.repository import ClassroomRepository
from app.classroom.domain.repository.classroom_material import (
    ClassroomMaterialRepository,
)
from app.classroom.domain.service import (
    ClassroomMaterialIngestPort,
    ClassroomMaterialIngestRequest,
)
from app.classroom.domain.usecase import ClassroomUseCase
from app.file.domain.entity.file import FileStatus
from app.file.domain.entity.file_download import FileDownload
from app.file.domain.service import FileUploadData
from app.file.domain.usecase.file import FileUseCase
from app.user.domain.entity import UserRole
from app.user.domain.repository import UserRepository
from core.db.transactional import transactional


class ClassroomService(ClassroomUseCase):
    def __init__(
        self,
        *,
        repository: ClassroomRepository,
        user_repository: UserRepository,
        material_repository: ClassroomMaterialRepository,
        file_usecase: FileUseCase,
        material_ingest_port: ClassroomMaterialIngestPort | None = None,
    ):
        self.repository = repository
        self.user_repository = user_repository
        self.material_repository = material_repository
        self.file_usecase = file_usecase
        self.material_ingest_port = material_ingest_port

    @transactional
    async def create_classroom(
        self,
        *,
        current_user: CurrentUser,
        command: CreateClassroomCommand,
    ) -> Classroom:
        if current_user.role not in (UserRole.PROFESSOR, UserRole.ADMIN):
            raise AuthForbiddenException()

        classroom = Classroom.create(
            organization_id=current_user.organization_id,
            name=command.name,
            professor_ids=command.professor_ids,
            current_user=current_user,
            grade=command.grade,
            semester=command.semester,
            section=command.section,
            description=command.description,
            student_ids=command.student_ids,
            allow_student_material_access=(
                command.allow_student_material_access
            ),
        )

        users = await self.user_repository.list_by_organization(
            classroom.organization_id
        )
        classroom.validate_members(
            {user.id: user for user in users if not user.is_deleted}
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

        if not classroom.can_be_accessed_by(current_user):
            raise AuthForbiddenException()

        return classroom

    async def get_manageable_classroom(
        self,
        *,
        classroom_id: UUID,
        current_user: CurrentUser,
    ) -> Classroom:
        if current_user.role not in (UserRole.PROFESSOR, UserRole.ADMIN):
            raise AuthForbiddenException()

        classroom = await self.get_classroom(
            classroom_id=classroom_id,
            current_user=current_user,
        )
        if not classroom.can_be_managed_by(current_user):
            raise AuthForbiddenException()
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
            if classroom.can_be_accessed_by(current_user)
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
            professor_ids = classroom.merge_professor_ids(
                command.professor_ids,
                current_user=current_user,
            )

        student_ids = classroom.student_ids
        if (
            "student_ids" in delivered_fields
            and command.student_ids is not None
        ):
            student_ids = classroom.normalized_student_ids(
                command.student_ids
            )

        classroom.update_details(
            name=name,
            grade=grade,
            semester=semester,
            section=section,
            description=command.description,
            replace_description="description" in delivered_fields,
            allow_student_material_access=(
                command.allow_student_material_access
            ),
            replace_allow_student_material_access=(
                "allow_student_material_access" in delivered_fields
                and command.allow_student_material_access is not None
            ),
            professor_ids=professor_ids,
            student_ids=student_ids,
        )

        users = await self.user_repository.list_by_organization(
            classroom.organization_id
        )
        classroom.validate_members(
            {user.id: user for user in users if not user.is_deleted}
        )

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

        duplicate_ids = classroom.find_duplicate_student_ids(
            command.student_ids
        )
        if duplicate_ids:
            raise ClassroomStudentAlreadyInvitedException(
                detail={
                    "student_ids": [str(user_id) for user_id in duplicate_ids]
                }
            )

        classroom.invite_students(command.student_ids)
        users = await self.user_repository.list_by_organization(
            classroom.organization_id
        )
        classroom.validate_students(
            {user.id: user for user in users if not user.is_deleted}
        )
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

        if not classroom.remove_student(command.student_id):
            raise ClassroomStudentNotEnrolledException(
                detail={"student_id": str(command.student_id)}
            )
        await self.repository.save(classroom)
        return classroom

    async def _ingest_material(
        self,
        *,
        classroom: Classroom,
        material: ClassroomMaterial,
        file,
    ) -> None:
        if self.material_ingest_port is None:
            return

        material.mark_ingest_pending()
        await self.material_repository.save(material)
        download = await self.file_usecase.get_file_download(file.id)
        try:
            ingest_result = await self.material_ingest_port.ingest_material(
                request=ClassroomMaterialIngestRequest(
                    material_id=material.id,
                    classroom_id=classroom.id,
                    title=material.title,
                    week=material.week,
                    description=material.description,
                    file_name=file.file_name,
                    mime_type=file.mime_type,
                    content=download.content.read(),
                )
            )
            if not ingest_result.scope_candidates:
                raise ClassroomMaterialIngestEmptyScopeDomainException()
            material.mark_ingest_completed(ingest_result.scope_candidates)
        except ClassroomMaterialIngestEmptyScopeDomainException as exc:
            material.mark_ingest_failed(exc.message)
        except ClassroomMaterialIngestDomainException as exc:
            material.mark_ingest_failed(exc.message)
        except Exception:
            material.mark_ingest_failed(
                "강의 자료 적재 중 오류가 발생했습니다."
            )
        await self.material_repository.save(material)

    @transactional
    async def create_classroom_material(
        self,
        *,
        classroom_id: UUID,
        current_user: CurrentUser,
        command: CreateClassroomMaterialCommand,
        file_upload: FileUploadData,
    ) -> ClassroomMaterialDetail:
        classroom = await self.get_manageable_classroom(
            classroom_id=classroom_id,
            current_user=current_user,
        )
        uploaded_file = await self.file_usecase.upload_file(
            file_upload=file_upload,
            directory=f"classrooms/{classroom.id}/materials",
            status=FileStatus.ACTIVE,
        )
        material = ClassroomMaterial.create(
            classroom_id=classroom.id,
            file_id=uploaded_file.id,
            title=command.title,
            week=command.week,
            description=command.description,
            uploaded_by=current_user.id,
        )
        await self.material_repository.save(material)
        await self._ingest_material(
            classroom=classroom,
            material=material,
            file=uploaded_file,
        )
        return ClassroomMaterialDetail(material=material, file=uploaded_file)

    async def list_classroom_materials(
        self,
        *,
        classroom_id: UUID,
        current_user: CurrentUser,
    ) -> list[ClassroomMaterialDetail]:
        classroom = await self.get_classroom(
            classroom_id=classroom_id,
            current_user=current_user,
        )
        if not classroom.allows_material_access_to(current_user):
            raise AuthForbiddenException()
        materials = await self.material_repository.list_by_classroom(
            classroom.id
        )
        result: list[ClassroomMaterialDetail] = []
        for material in materials:
            file = await self.file_usecase.get_file(material.file_id)
            result.append(ClassroomMaterialDetail(material=material, file=file))
        return result

    async def get_classroom_material(
        self,
        *,
        classroom_id: UUID,
        material_id: UUID,
        current_user: CurrentUser,
    ) -> ClassroomMaterialDetail:
        classroom = await self.get_classroom(
            classroom_id=classroom_id,
            current_user=current_user,
        )
        if not classroom.allows_material_access_to(current_user):
            raise AuthForbiddenException()
        material = await self.material_repository.get_by_id(material_id)
        if material is None or not material.belongs_to(classroom.id):
            raise ClassroomMaterialNotFoundException()
        file = await self.file_usecase.get_file(material.file_id)
        return ClassroomMaterialDetail(material=material, file=file)

    async def get_classroom_material_download(
        self,
        *,
        classroom_id: UUID,
        material_id: UUID,
        current_user: CurrentUser,
    ) -> FileDownload:
        result = await self.get_classroom_material(
            classroom_id=classroom_id,
            material_id=material_id,
            current_user=current_user,
        )
        return await self.file_usecase.get_file_download(result.file.id)

    @transactional
    async def update_classroom_material(
        self,
        *,
        classroom_id: UUID,
        material_id: UUID,
        current_user: CurrentUser,
        command: UpdateClassroomMaterialCommand,
        file_upload: FileUploadData | None = None,
    ) -> ClassroomMaterialDetail:
        classroom = await self.get_manageable_classroom(
            classroom_id=classroom_id,
            current_user=current_user,
        )
        material = await self.material_repository.get_by_id(material_id)
        if material is None or not material.belongs_to(classroom.id):
            raise ClassroomMaterialNotFoundException()

        delivered_fields = command.model_fields_set
        original_title = material.title
        original_week = material.week
        original_description = material.description
        next_title = (
            command.title if "title" in delivered_fields else original_title
        )
        next_week = (
            command.week if "week" in delivered_fields else original_week
        )
        next_description = (
            command.description
            if "description" in delivered_fields
            else original_description
        )
        metadata_changed = (
            next_title != original_title
            or next_week != original_week
            or next_description != original_description
        )

        material.update(
            title=command.title if "title" in delivered_fields else None,
            week=command.week if "week" in delivered_fields else None,
            description=command.description,
            replace_description="description" in delivered_fields,
        )

        if file_upload is not None:
            replacement_file = await self.file_usecase.upload_file(
                file_upload=file_upload,
                directory=f"classrooms/{classroom.id}/materials",
                status=FileStatus.ACTIVE,
            )
            old_file_id = material.replace_file(replacement_file.id)
            await self.material_repository.save(material)
            await self._ingest_material(
                classroom=classroom,
                material=material,
                file=replacement_file,
            )
            await self.file_usecase.delete_file(old_file_id)
            return ClassroomMaterialDetail(
                material=material,
                file=replacement_file,
            )

        file = await self.file_usecase.get_file(material.file_id)
        if metadata_changed and self.material_ingest_port is not None:
            await self._ingest_material(
                classroom=classroom,
                material=material,
                file=file,
            )
            return ClassroomMaterialDetail(material=material, file=file)

        await self.material_repository.save(material)
        return ClassroomMaterialDetail(material=material, file=file)

    @transactional
    async def reingest_classroom_material(
        self,
        *,
        classroom_id: UUID,
        material_id: UUID,
        current_user: CurrentUser,
    ) -> ClassroomMaterialDetail:
        classroom = await self.get_manageable_classroom(
            classroom_id=classroom_id,
            current_user=current_user,
        )
        material = await self.material_repository.get_by_id(material_id)
        if material is None or not material.belongs_to(classroom.id):
            raise ClassroomMaterialNotFoundException()

        file = await self.file_usecase.get_file(material.file_id)
        await self._ingest_material(
            classroom=classroom,
            material=material,
            file=file,
        )
        return ClassroomMaterialDetail(material=material, file=file)

    @transactional
    async def delete_classroom_material(
        self,
        *,
        classroom_id: UUID,
        material_id: UUID,
        current_user: CurrentUser,
    ) -> ClassroomMaterialDetail:
        classroom = await self.get_manageable_classroom(
            classroom_id=classroom_id,
            current_user=current_user,
        )
        material = await self.material_repository.get_by_id(material_id)
        if material is None or not material.belongs_to(classroom.id):
            raise ClassroomMaterialNotFoundException()

        file = await self.file_usecase.get_file(material.file_id)
        result = ClassroomMaterialDetail(material=material, file=file)
        await self.material_repository.delete(material)
        await self.file_usecase.delete_file(material.file_id)
        return result
