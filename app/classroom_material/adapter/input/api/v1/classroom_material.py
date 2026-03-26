from uuid import UUID

from dependency_injector.wiring import Provide, inject
from fastapi import APIRouter, Depends, File, Form, UploadFile
from fastapi.exceptions import RequestValidationError
from fastapi.responses import StreamingResponse
from pydantic import ValidationError

from app.auth.domain.entity import CurrentUser
from app.classroom_material.adapter.input.api.v1.request import (
    CreateClassroomMaterialRequest,
    UpdateClassroomMaterialRequest,
)
from app.classroom_material.adapter.input.api.v1.response import (
    ClassroomMaterialFilePayload,
    ClassroomMaterialListResponse,
    ClassroomMaterialPayload,
    ClassroomMaterialResponse,
)
from app.classroom_material.container import ClassroomMaterialContainer
from app.classroom_material.domain.command import (
    CreateClassroomMaterialCommand,
    UpdateClassroomMaterialCommand,
)
from app.classroom_material.domain.usecase import ClassroomMaterialUseCase
from app.file.domain.service import FileUploadData
from core.fastapi.dependencies import (
    IsAuthenticated,
    IsProfessorOrAdmin,
    PermissionDependency,
    get_current_user,
)

router = APIRouter(
    prefix="/classrooms/{classroom_id}/materials", tags=["classroom-materials"]
)


def _iter_content(content, chunk_size: int = 64 * 1024):
    while True:
        chunk = content.read(chunk_size)
        if not chunk:
            break
        yield chunk
    close = getattr(content, "close", None)
    if callable(close):
        close()


@router.post(
    "",
    response_model=ClassroomMaterialResponse,
    dependencies=[Depends(PermissionDependency([IsProfessorOrAdmin]))],
)
@inject
async def create_classroom_material(
    classroom_id: UUID,
    title: str = Form(...),
    week: int = Form(...),
    description: str | None = Form(None),
    uploaded_file: UploadFile = File(...),
    current_user: CurrentUser = Depends(get_current_user),
    usecase: ClassroomMaterialUseCase = Depends(
        Provide[ClassroomMaterialContainer.service]
    ),
):
    try:
        request = CreateClassroomMaterialRequest(
            title=title,
            week=week,
            description=description,
        )
    except ValidationError as exc:
        raise RequestValidationError(exc.errors()) from exc

    result = await usecase.create_classroom_material(
        classroom_id=classroom_id,
        current_user=current_user,
        command=CreateClassroomMaterialCommand(
            **request.model_dump(),
        ),
        file_upload=FileUploadData(
            file_name=uploaded_file.filename or "uploaded-file",
            mime_type=(
                uploaded_file.content_type or "application/octet-stream"
            ),
            content=uploaded_file.file,
        ),
    )
    return ClassroomMaterialResponse(
        data=ClassroomMaterialPayload(
            id=str(result.material.id),
            classroom_id=str(result.material.classroom_id),
            title=result.material.title,
            week=result.material.week,
            description=result.material.description,
            uploaded_by=str(result.material.uploaded_by),
            uploaded_at=result.material.created_at,
            file=ClassroomMaterialFilePayload(
                id=str(result.file.id),
                file_name=result.file.file_name,
                file_path=result.file.file_path,
                file_extension=result.file.file_extension,
                file_size=result.file.file_size,
                mime_type=result.file.mime_type,
            ),
        )
    )


@router.get(
    "",
    response_model=ClassroomMaterialListResponse,
    dependencies=[Depends(PermissionDependency([IsAuthenticated]))],
)
@inject
async def list_classroom_materials(
    classroom_id: UUID,
    current_user: CurrentUser = Depends(get_current_user),
    usecase: ClassroomMaterialUseCase = Depends(
        Provide[ClassroomMaterialContainer.service]
    ),
):
    results = await usecase.list_classroom_materials(
        classroom_id=classroom_id,
        current_user=current_user,
    )
    return ClassroomMaterialListResponse(
        data=[
            ClassroomMaterialPayload(
                id=str(result.material.id),
                classroom_id=str(result.material.classroom_id),
                title=result.material.title,
                week=result.material.week,
                description=result.material.description,
                uploaded_by=str(result.material.uploaded_by),
                uploaded_at=result.material.created_at,
                file=ClassroomMaterialFilePayload(
                    id=str(result.file.id),
                    file_name=result.file.file_name,
                    file_path=result.file.file_path,
                    file_extension=result.file.file_extension,
                    file_size=result.file.file_size,
                    mime_type=result.file.mime_type,
                ),
            )
            for result in results
        ]
    )


@router.get(
    "/{material_id}",
    response_model=ClassroomMaterialResponse,
    dependencies=[Depends(PermissionDependency([IsAuthenticated]))],
)
@inject
async def get_classroom_material(
    classroom_id: UUID,
    material_id: UUID,
    current_user: CurrentUser = Depends(get_current_user),
    usecase: ClassroomMaterialUseCase = Depends(
        Provide[ClassroomMaterialContainer.service]
    ),
):
    result = await usecase.get_classroom_material(
        classroom_id=classroom_id,
        material_id=material_id,
        current_user=current_user,
    )
    return ClassroomMaterialResponse(
        data=ClassroomMaterialPayload(
            id=str(result.material.id),
            classroom_id=str(result.material.classroom_id),
            title=result.material.title,
            week=result.material.week,
            description=result.material.description,
            uploaded_by=str(result.material.uploaded_by),
            uploaded_at=result.material.created_at,
            file=ClassroomMaterialFilePayload(
                id=str(result.file.id),
                file_name=result.file.file_name,
                file_path=result.file.file_path,
                file_extension=result.file.file_extension,
                file_size=result.file.file_size,
                mime_type=result.file.mime_type,
            ),
        )
    )


@router.get(
    "/{material_id}/download",
    dependencies=[Depends(PermissionDependency([IsAuthenticated]))],
)
@inject
async def download_classroom_material(
    classroom_id: UUID,
    material_id: UUID,
    current_user: CurrentUser = Depends(get_current_user),
    usecase: ClassroomMaterialUseCase = Depends(
        Provide[ClassroomMaterialContainer.service]
    ),
):
    download = await usecase.get_classroom_material_download(
        classroom_id=classroom_id,
        material_id=material_id,
        current_user=current_user,
    )
    return StreamingResponse(
        _iter_content(download.content),
        media_type=download.mime_type,
        headers={
            "Content-Disposition": (
                f'attachment; filename="{download.file_name}"'
            )
        },
    )


@router.patch(
    "/{material_id}",
    response_model=ClassroomMaterialResponse,
    dependencies=[Depends(PermissionDependency([IsProfessorOrAdmin]))],
)
@inject
async def update_classroom_material(
    classroom_id: UUID,
    material_id: UUID,
    title: str | None = Form(None),
    week: int | None = Form(None),
    description: str | None = Form(None),
    uploaded_file: UploadFile | None = File(None),
    current_user: CurrentUser = Depends(get_current_user),
    usecase: ClassroomMaterialUseCase = Depends(
        Provide[ClassroomMaterialContainer.service]
    ),
):
    request_data = {
        key: value
        for key, value in {
            "title": title,
            "week": week,
            "description": description,
        }.items()
        if value is not None
    }

    request = None
    if request_data:
        try:
            request = UpdateClassroomMaterialRequest(**request_data)
        except ValidationError as exc:
            raise RequestValidationError(exc.errors()) from exc
    elif uploaded_file is None:
        try:
            UpdateClassroomMaterialRequest(**request_data)
        except ValidationError as exc:
            raise RequestValidationError([
                {
                    "type": "value_error",
                    "loc": ("body",),
                    "msg": "최소 하나 이상의 수정 필드가 필요합니다.",
                    "input": None,
                }
            ]) from exc

    result = await usecase.update_classroom_material(
        classroom_id=classroom_id,
        material_id=material_id,
        current_user=current_user,
        command=UpdateClassroomMaterialCommand(
            **(
                request.model_dump(exclude_unset=True)
                if request is not None
                else {}
            )
        ),
        file_upload=(
            FileUploadData(
                file_name=uploaded_file.filename or "uploaded-file",
                mime_type=(
                    uploaded_file.content_type or "application/octet-stream"
                ),
                content=uploaded_file.file,
            )
            if uploaded_file is not None
            else None
        ),
    )
    return ClassroomMaterialResponse(
        data=ClassroomMaterialPayload(
            id=str(result.material.id),
            classroom_id=str(result.material.classroom_id),
            title=result.material.title,
            week=result.material.week,
            description=result.material.description,
            uploaded_by=str(result.material.uploaded_by),
            uploaded_at=result.material.created_at,
            file=ClassroomMaterialFilePayload(
                id=str(result.file.id),
                file_name=result.file.file_name,
                file_path=result.file.file_path,
                file_extension=result.file.file_extension,
                file_size=result.file.file_size,
                mime_type=result.file.mime_type,
            ),
        )
    )


@router.delete(
    "/{material_id}",
    response_model=ClassroomMaterialResponse,
    dependencies=[Depends(PermissionDependency([IsProfessorOrAdmin]))],
)
@inject
async def delete_classroom_material(
    classroom_id: UUID,
    material_id: UUID,
    current_user: CurrentUser = Depends(get_current_user),
    usecase: ClassroomMaterialUseCase = Depends(
        Provide[ClassroomMaterialContainer.service]
    ),
):
    result = await usecase.delete_classroom_material(
        classroom_id=classroom_id,
        material_id=material_id,
        current_user=current_user,
    )
    return ClassroomMaterialResponse(
        data=ClassroomMaterialPayload(
            id=str(result.material.id),
            classroom_id=str(result.material.classroom_id),
            title=result.material.title,
            week=result.material.week,
            description=result.material.description,
            uploaded_by=str(result.material.uploaded_by),
            uploaded_at=result.material.created_at,
            file=ClassroomMaterialFilePayload(
                id=str(result.file.id),
                file_name=result.file.file_name,
                file_path=result.file.file_path,
                file_extension=result.file.file_extension,
                file_size=result.file.file_size,
                mime_type=result.file.mime_type,
            ),
        )
    )
