from uuid import UUID

from app.auth.application.exception import AuthForbiddenException
from app.auth.domain.entity import CurrentUser
from app.classroom.domain.usecase import ClassroomUseCase
from app.classroom_material.application.dto import ClassroomMaterialResult
from app.classroom_material.application.exception import (
    ClassroomMaterialNotFoundException,
)
from app.classroom_material.domain.command import (
    CreateClassroomMaterialCommand,
    UpdateClassroomMaterialCommand,
)
from app.classroom_material.domain.entity import ClassroomMaterial
from app.classroom_material.domain.repository import ClassroomMaterialRepository
from app.classroom_material.domain.usecase import ClassroomMaterialUseCase
from app.file.domain.entity.file import FileStatus
from app.file.domain.service import FileUploadData
from app.file.domain.usecase.file import FileUseCase
from app.user.domain.entity import UserRole
from core.db.transactional import transactional


class ClassroomMaterialService(ClassroomMaterialUseCase):
    def __init__(
        self,
        *,
        repository: ClassroomMaterialRepository,
        classroom_usecase: ClassroomUseCase,
        file_usecase: FileUseCase,
    ):
        self.repository = repository
        self.classroom_usecase = classroom_usecase
        self.file_usecase = file_usecase

    @transactional
    async def create_classroom_material(
        self,
        *,
        classroom_id: UUID,
        current_user: CurrentUser,
        command: CreateClassroomMaterialCommand,
        file_upload: FileUploadData,
    ) -> ClassroomMaterialResult:
        classroom = await self.classroom_usecase.get_manageable_classroom(
            classroom_id=classroom_id,
            current_user=current_user,
        )
        uploaded_file = await self.file_usecase.upload_file(
            file_upload=file_upload,
            directory=f"classrooms/{classroom.id}/materials",
            status=FileStatus.ACTIVE,
        )
        material = ClassroomMaterial(
            classroom_id=classroom.id,
            file_id=uploaded_file.id,
            title=command.title,
            week=command.week,
            description=command.description,
            uploaded_by=current_user.id,
        )
        saved_material = await self.repository.save(material)
        return ClassroomMaterialResult(
            material=saved_material, file=uploaded_file
        )

    async def list_classroom_materials(
        self,
        *,
        classroom_id: UUID,
        current_user: CurrentUser,
    ) -> list[ClassroomMaterialResult]:
        classroom = await self.classroom_usecase.get_classroom(
            classroom_id=classroom_id,
            current_user=current_user,
        )
        self._ensure_student_material_access(classroom, current_user)
        materials = await self.repository.list_by_classroom(classroom.id)
        return [await self._to_result(material) for material in materials]

    async def get_classroom_material(
        self,
        *,
        classroom_id: UUID,
        material_id: UUID,
        current_user: CurrentUser,
    ) -> ClassroomMaterialResult:
        classroom = await self.classroom_usecase.get_classroom(
            classroom_id=classroom_id,
            current_user=current_user,
        )
        self._ensure_student_material_access(classroom, current_user)
        material = await self._get_material(material_id)
        if material.classroom_id != classroom.id:
            raise ClassroomMaterialNotFoundException()
        return await self._to_result(material)

    @transactional
    async def update_classroom_material(
        self,
        *,
        classroom_id: UUID,
        material_id: UUID,
        current_user: CurrentUser,
        command: UpdateClassroomMaterialCommand,
        file_upload: FileUploadData | None = None,
    ) -> ClassroomMaterialResult:
        classroom = await self.classroom_usecase.get_manageable_classroom(
            classroom_id=classroom_id,
            current_user=current_user,
        )
        material = await self._get_material(material_id)
        if material.classroom_id != classroom.id:
            raise ClassroomMaterialNotFoundException()

        delivered_fields = command.model_fields_set
        if "title" in delivered_fields and command.title is not None:
            material.title = command.title
        if "week" in delivered_fields and command.week is not None:
            material.week = command.week
        if "description" in delivered_fields:
            material.description = command.description

        if file_upload is not None:
            replacement_file = await self.file_usecase.upload_file(
                file_upload=file_upload,
                directory=f"classrooms/{classroom.id}/materials",
                status=FileStatus.ACTIVE,
            )
            old_file_id = material.file_id
            material.file_id = replacement_file.id
            saved_material = await self.repository.save(material)
            await self.file_usecase.delete_file(old_file_id)
            return ClassroomMaterialResult(
                material=saved_material,
                file=replacement_file,
            )

        saved_material = await self.repository.save(material)
        return await self._to_result(saved_material)

    @transactional
    async def delete_classroom_material(
        self,
        *,
        classroom_id: UUID,
        material_id: UUID,
        current_user: CurrentUser,
    ) -> ClassroomMaterialResult:
        classroom = await self.classroom_usecase.get_manageable_classroom(
            classroom_id=classroom_id,
            current_user=current_user,
        )
        material = await self._get_material(material_id)
        if material.classroom_id != classroom.id:
            raise ClassroomMaterialNotFoundException()

        result = await self._to_result(material)
        await self.repository.delete(material)
        await self.file_usecase.delete_file(material.file_id)
        return result

    async def _to_result(
        self,
        material: ClassroomMaterial,
    ) -> ClassroomMaterialResult:
        file = await self.file_usecase.get_file(material.file_id)
        return ClassroomMaterialResult(material=material, file=file)

    async def _get_material(self, material_id: UUID) -> ClassroomMaterial:
        material = await self.repository.get_by_id(material_id)
        if material is None:
            raise ClassroomMaterialNotFoundException()
        return material

    @staticmethod
    def _ensure_student_material_access(
        classroom, current_user: CurrentUser
    ) -> None:
        if current_user.role != UserRole.STUDENT:
            return
        if classroom.allow_student_material_access:
            return
        raise AuthForbiddenException()
