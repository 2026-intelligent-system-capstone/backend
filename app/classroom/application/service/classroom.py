from typing import Any
from uuid import UUID

from app.async_job.application.service import AsyncJobService
from app.async_job.domain.entity import AsyncJobTargetType, AsyncJobType
from app.auth.application.exception import AuthForbiddenException
from app.auth.domain.entity import CurrentUser
from app.classroom.application.exception import (
    ClassroomAlreadyExistsException,
    ClassroomMaterialDownloadUnavailableException,
    ClassroomMaterialInvalidSourceException,
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
    ClassroomMaterialIngestCapability,
    ClassroomMaterialSourceKind,
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
    validate_classroom_material_source_url,
)
from app.classroom.domain.usecase import ClassroomUseCase
from app.file.domain.entity.file import File, FileStatus
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
        async_job_service: AsyncJobService | None = None,
    ):
        self.repository = repository
        self.user_repository = user_repository
        self.material_repository = material_repository
        self.file_usecase = file_usecase
        self.material_ingest_port = material_ingest_port
        self.async_job_service = async_job_service

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
        classroom.validate_members({
            user.id: user for user in users if not user.is_deleted
        })

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
            student_ids = classroom.normalized_student_ids(command.student_ids)

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
        classroom.validate_members({
            user.id: user for user in users if not user.is_deleted
        })

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
        classroom.validate_students({
            user.id: user for user in users if not user.is_deleted
        })
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

    def _build_ingest_capability(
        self,
        *,
        source_kind: ClassroomMaterialSourceKind,
    ) -> ClassroomMaterialIngestCapability:
        if source_kind in (
            ClassroomMaterialSourceKind.FILE,
            ClassroomMaterialSourceKind.LINK,
        ):
            return ClassroomMaterialIngestCapability(supported=True)
        return ClassroomMaterialIngestCapability(
            supported=False,
            reason="현재 지원하지 않는 강의 자료 형식입니다.",
        )

    def _build_file_ingest_metadata(self, *, mime_type: str) -> dict[str, Any]:
        return {"mime_type": mime_type}

    def _build_link_ingest_metadata(self, *, source_url: str) -> dict[str, Any]:
        return {"source_url": source_url}

    def _validate_link_source_url(self, *, source_url: str) -> None:
        try:
            validate_classroom_material_source_url(source_url)
        except ClassroomMaterialIngestDomainException as exc:
            raise ClassroomMaterialInvalidSourceException(
                message=exc.message
            ) from exc

    async def _enqueue_material_ingest(
        self,
        *,
        classroom: Classroom,
        material: ClassroomMaterial,
        current_user: CurrentUser,
        file: File | None,
    ) -> None:
        if self.async_job_service is None or not material.supports_ingest():
            await self._ingest_material(
                classroom=classroom,
                material=material,
                file=file,
            )
            return

        material.mark_ingest_pending()
        await self.material_repository.save(material)
        await self.async_job_service.enqueue(
            job_type=AsyncJobType.MATERIAL_INGEST,
            target_type=AsyncJobTargetType.CLASSROOM_MATERIAL,
            target_id=material.id,
            requested_by=current_user.id,
            payload={
                "classroom_id": str(classroom.id),
                "material_id": str(material.id),
                "file_id": str(file.id) if file is not None else None,
            },
        )

    async def _ingest_material(
        self,
        *,
        classroom: Classroom,
        material: ClassroomMaterial,
        file: File | None,
    ) -> None:
        if self.material_ingest_port is None or not material.supports_ingest():
            return

        if file is None:
            if (
                material.source_kind is not ClassroomMaterialSourceKind.LINK
                or material.source_url is None
            ):
                raise ClassroomMaterialInvalidSourceException(
                    message="적재 가능한 자료에 원본 정보가 없습니다."
                )
        else:
            download = await self.file_usecase.get_file_download(file.id)
            ingest_request = ClassroomMaterialIngestRequest(
                material_id=material.id,
                classroom_id=classroom.id,
                title=material.title,
                week=material.week,
                description=material.description,
                source_kind=material.source_kind,
                file_name=file.file_name,
                mime_type=file.mime_type,
                content=download.content.read(),
                source_url=material.source_url,
            )

        material.mark_ingest_pending()
        await self.material_repository.save(material)
        try:
            if file is None:
                validate_classroom_material_source_url(material.source_url)
                ingest_request = ClassroomMaterialIngestRequest(
                    material_id=material.id,
                    classroom_id=classroom.id,
                    title=material.title,
                    week=material.week,
                    description=material.description,
                    source_kind=material.source_kind,
                    file_name=material.source_url,
                    mime_type="text/plain",
                    content=material.source_url.encode(),
                    source_url=material.source_url,
                )
            ingest_result = await self.material_ingest_port.ingest_material(
                request=ingest_request
            )
            if (
                not ingest_result.scope_candidates
                and material.source_kind is ClassroomMaterialSourceKind.FILE
            ):
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

    async def _get_material_file(
        self, material: ClassroomMaterial
    ) -> ClassroomMaterialDetail:
        if material.file_id is None:
            return ClassroomMaterialDetail(material=material, file=None)
        file = await self.file_usecase.get_file(material.file_id)
        return ClassroomMaterialDetail(material=material, file=file)

    @transactional
    async def create_classroom_material(
        self,
        *,
        classroom_id: UUID,
        current_user: CurrentUser,
        command: CreateClassroomMaterialCommand,
        file_upload: FileUploadData | None = None,
    ) -> ClassroomMaterialDetail:
        classroom = await self.get_manageable_classroom(
            classroom_id=classroom_id,
            current_user=current_user,
        )
        if command.source_kind is ClassroomMaterialSourceKind.FILE:
            if file_upload is None:
                raise ClassroomMaterialInvalidSourceException(
                    message="파일 자료에는 업로드 파일이 필요합니다."
                )
            uploaded_file = await self.file_usecase.upload_file(
                file_upload=file_upload,
                directory=f"classrooms/{classroom.id}/materials",
                status=FileStatus.ACTIVE,
            )
            material = ClassroomMaterial.create_file(
                classroom_id=classroom.id,
                file_id=uploaded_file.id,
                title=command.title,
                week=command.week,
                description=command.description,
                uploaded_by=current_user.id,
                original_file=uploaded_file,
                ingest_capability=self._build_ingest_capability(
                    source_kind=command.source_kind
                ),
                ingest_metadata=self._build_file_ingest_metadata(
                    mime_type=uploaded_file.mime_type
                ),
            )
            await self.material_repository.save(material)
            await self._enqueue_material_ingest(
                classroom=classroom,
                material=material,
                current_user=current_user,
                file=uploaded_file,
            )
            return ClassroomMaterialDetail(
                material=material, file=uploaded_file
            )

        if command.source_kind is ClassroomMaterialSourceKind.LINK:
            if file_upload is not None:
                raise ClassroomMaterialInvalidSourceException(
                    message="링크 자료에는 업로드 파일을 함께 보낼 수 없습니다."
                )
            if command.source_url is None:
                raise ClassroomMaterialInvalidSourceException(
                    message="링크 자료에는 source_url이 필요합니다."
                )
            self._validate_link_source_url(source_url=command.source_url)
            material = ClassroomMaterial.create_link(
                classroom_id=classroom.id,
                source_url=command.source_url,
                title=command.title,
                week=command.week,
                description=command.description,
                uploaded_by=current_user.id,
                ingest_capability=self._build_ingest_capability(
                    source_kind=command.source_kind
                ),
                ingest_metadata=self._build_link_ingest_metadata(
                    source_url=command.source_url
                ),
            )
            await self.material_repository.save(material)
            await self._enqueue_material_ingest(
                classroom=classroom,
                material=material,
                current_user=current_user,
                file=None,
            )
            return ClassroomMaterialDetail(material=material, file=None)

        raise ClassroomMaterialInvalidSourceException()

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
            result.append(await self._get_material_file(material))
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
        return await self._get_material_file(material)

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
        if result.file is None:
            raise ClassroomMaterialDownloadUnavailableException()
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
        original_source_url = material.source_url

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
        target_source_kind = (
            command.source_kind
            if "source_kind" in delivered_fields
            and command.source_kind is not None
            else material.source_kind
        )
        next_source_url = (
            command.source_url
            if "source_url" in delivered_fields
            else original_source_url
        )
        metadata_changed = (
            next_title != original_title
            or next_week != original_week
            or next_description != original_description
            or next_source_url != original_source_url
        )
        source_kind_changed = target_source_kind is not material.source_kind

        if target_source_kind is ClassroomMaterialSourceKind.LINK:
            if file_upload is not None:
                raise ClassroomMaterialInvalidSourceException(
                    message="링크 자료에는 업로드 파일을 함께 보낼 수 없습니다."
                )
            if next_source_url is None:
                raise ClassroomMaterialInvalidSourceException(
                    message="링크 자료에는 source_url이 필요합니다."
                )
            self._validate_link_source_url(source_url=next_source_url)

        if (
            target_source_kind is ClassroomMaterialSourceKind.FILE
            and file_upload is None
            and (source_kind_changed or material.file_id is None)
        ):
            raise ClassroomMaterialInvalidSourceException(
                message="파일 자료로 변경 시 uploaded_file이 필요합니다."
            )

        material.update(
            title=command.title if "title" in delivered_fields else None,
            week=command.week if "week" in delivered_fields else None,
            description=command.description,
            replace_description="description" in delivered_fields,
            source_url=(
                command.source_url
                if target_source_kind is ClassroomMaterialSourceKind.LINK
                else None
            ),
            replace_source_url=(
                (
                    "source_url" in delivered_fields
                    and target_source_kind is ClassroomMaterialSourceKind.LINK
                )
                or target_source_kind is ClassroomMaterialSourceKind.FILE
            ),
        )

        if target_source_kind is ClassroomMaterialSourceKind.LINK:
            old_file_id = None
            if source_kind_changed:
                old_file_id = material.switch_to_link(
                    source_url=next_source_url,
                    ingest_capability=self._build_ingest_capability(
                        source_kind=target_source_kind
                    ),
                    ingest_metadata=self._build_link_ingest_metadata(
                        source_url=next_source_url
                    ),
                )
            else:
                material.update(
                    ingest_capability=self._build_ingest_capability(
                        source_kind=target_source_kind
                    ),
                    replace_ingest_capability=True,
                    ingest_metadata=self._build_link_ingest_metadata(
                        source_url=next_source_url
                    ),
                    replace_ingest_metadata=True,
                )
            await self.material_repository.save(material)
            if metadata_changed and material.supports_ingest():
                await self._enqueue_material_ingest(
                    classroom=classroom,
                    material=material,
                    current_user=current_user,
                    file=None,
                )
            if old_file_id is not None:
                await self.file_usecase.delete_file(old_file_id)
            return ClassroomMaterialDetail(material=material, file=None)

        if target_source_kind is not ClassroomMaterialSourceKind.FILE:
            raise ClassroomMaterialInvalidSourceException()

        if file_upload is not None:
            replacement_file = await self.file_usecase.upload_file(
                file_upload=file_upload,
                directory=f"classrooms/{classroom.id}/materials",
                status=FileStatus.ACTIVE,
            )
            old_file_id = material.replace_file(
                file_id=replacement_file.id,
                original_file=replacement_file,
                ingest_capability=self._build_ingest_capability(
                    source_kind=target_source_kind
                ),
                ingest_metadata=self._build_file_ingest_metadata(
                    mime_type=replacement_file.mime_type
                ),
            )
            await self.material_repository.save(material)
            await self._enqueue_material_ingest(
                classroom=classroom,
                material=material,
                current_user=current_user,
                file=replacement_file,
            )
            if old_file_id is not None:
                await self.file_usecase.delete_file(old_file_id)
            return ClassroomMaterialDetail(
                material=material,
                file=replacement_file,
            )

        if material.file_id is None:
            raise ClassroomMaterialInvalidSourceException(
                message="파일 자료로 변경 시 uploaded_file이 필요합니다."
            )

        file = await self.file_usecase.get_file(material.file_id)
        material.update(
            ingest_capability=self._build_ingest_capability(
                source_kind=target_source_kind
            ),
            replace_ingest_capability=True,
            ingest_metadata=self._build_file_ingest_metadata(
                mime_type=file.mime_type
            ),
            replace_ingest_metadata=True,
        )
        if metadata_changed and material.supports_ingest():
            await self._enqueue_material_ingest(
                classroom=classroom,
                material=material,
                current_user=current_user,
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

        result = await self._get_material_file(material)
        if material.source_kind is ClassroomMaterialSourceKind.LINK:
            if material.source_url is None:
                raise ClassroomMaterialInvalidSourceException(
                    message="링크 자료에는 source_url이 필요합니다."
                )
            self._validate_link_source_url(source_url=material.source_url)
        await self._enqueue_material_ingest(
            classroom=classroom,
            material=material,
            current_user=current_user,
            file=result.file,
        )
        return ClassroomMaterialDetail(material=material, file=result.file)

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

        result = await self._get_material_file(material)
        await self.material_repository.delete(material)
        if material.file_id is not None:
            await self.file_usecase.delete_file(material.file_id)
        return result
