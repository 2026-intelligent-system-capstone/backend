from datetime import UTC, datetime
from uuid import UUID

from dependency_injector.wiring import Provide, inject
from fastapi import APIRouter, Depends, File, Form, UploadFile
from fastapi.exceptions import RequestValidationError
from fastapi.responses import StreamingResponse
from pydantic import ValidationError

from app.auth.domain.entity import CurrentUser
from app.classroom.adapter.input.api.v1.request import (
    CreateClassroomMaterialRequest,
    UpdateClassroomMaterialRequest,
)
from app.classroom.adapter.input.api.v1.response import (
    ClassroomMaterialFilePayload,
    ClassroomMaterialIngestCapabilityPayload,
    ClassroomMaterialListResponse,
    ClassroomMaterialOriginalFilePayload,
    ClassroomMaterialPayload,
    ClassroomMaterialResponse,
    ClassroomMaterialScopeCandidatePayload,
)
from app.classroom.container import ClassroomContainer
from app.classroom.domain.command import (
    CreateClassroomMaterialCommand,
    UpdateClassroomMaterialCommand,
)
from app.classroom.domain.entity import ClassroomMaterialSourceKind
from app.classroom.domain.usecase import ClassroomUseCase
from app.file.domain.service import FileUploadData
from core.fastapi.dependencies import (
    IsAuthenticated,
    IsProfessorOrAdmin,
    PermissionDependency,
    get_current_user,
)

router = APIRouter(
    prefix="/classrooms/{classroom_id}/materials",
    tags=["classroom-materials"],
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


def _build_uploaded_at(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _build_classroom_material_payload(result) -> ClassroomMaterialPayload:
    original_file = result.material.get_original_file()
    ingest_capability = result.material.get_ingest_capability()
    return ClassroomMaterialPayload(
        id=str(result.material.id),
        classroom_id=str(result.material.classroom_id),
        title=result.material.title,
        week=result.material.week,
        description=result.material.description,
        uploaded_by=str(result.material.uploaded_by),
        uploaded_at=_build_uploaded_at(result.material.created_at),
        source_kind=result.material.source_kind.value,
        source_url=result.material.source_url,
        ingest_status=result.material.ingest_status.value,
        ingest_error=result.material.ingest_error,
        ingest_capability=ClassroomMaterialIngestCapabilityPayload(
            supported=ingest_capability.supported,
            reason=ingest_capability.reason,
        ),
        ingest_metadata=result.material.ingest_metadata,
        scope_candidates=[
            ClassroomMaterialScopeCandidatePayload(
                label=candidate.label,
                scope_text=candidate.scope_text,
                keywords=candidate.keywords,
                week_range=candidate.week_range,
                confidence=candidate.confidence,
            )
            for candidate in result.material.get_scope_candidates()
        ],
        file=(
            ClassroomMaterialFilePayload(
                id=str(result.file.id),
                file_name=result.file.file_name,
                file_path=result.file.file_path,
                file_extension=result.file.file_extension,
                file_size=result.file.file_size,
                mime_type=result.file.mime_type,
            )
            if result.file is not None
            else None
        ),
        original_file=(
            ClassroomMaterialOriginalFilePayload(
                file_name=original_file.file_name,
                file_path=original_file.file_path,
                file_extension=original_file.file_extension,
                file_size=original_file.file_size,
                mime_type=original_file.mime_type,
            )
            if original_file is not None
            else None
        ),
    )


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
    source_kind: ClassroomMaterialSourceKind = Form(
        ClassroomMaterialSourceKind.FILE
    ),
    source_url: str | None = Form(None),
    uploaded_file: UploadFile | None = File(None),
    current_user: CurrentUser = Depends(get_current_user),
    usecase: ClassroomUseCase = Depends(Provide[ClassroomContainer.service]),
):
    normalized_description = (
        description.strip() or None if description is not None else None
    )
    normalized_source_url = (
        source_url.strip() or None if source_url is not None else None
    )
    try:
        request = CreateClassroomMaterialRequest(
            title=title,
            week=week,
            description=normalized_description,
            source_kind=source_kind,
            source_url=normalized_source_url,
        )
    except ValidationError as exc:
        raise RequestValidationError(exc.errors()) from exc

    if (
        source_kind is ClassroomMaterialSourceKind.FILE
        and uploaded_file is None
    ):
        raise RequestValidationError([
            {
                "type": "missing",
                "loc": ("body", "uploaded_file"),
                "msg": "Field required",
                "input": None,
            }
        ])
    if (
        source_kind is ClassroomMaterialSourceKind.LINK
        and uploaded_file is not None
    ):
        raise RequestValidationError([
            {
                "type": "value_error",
                "loc": ("body", "uploaded_file"),
                "msg": "링크 자료에는 uploaded_file을 함께 보낼 수 없습니다.",
                "input": uploaded_file.filename,
            }
        ])

    result = await usecase.create_classroom_material(
        classroom_id=classroom_id,
        current_user=current_user,
        command=CreateClassroomMaterialCommand(
            **request.model_dump(mode="json")
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
        data=_build_classroom_material_payload(result)
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
    usecase: ClassroomUseCase = Depends(Provide[ClassroomContainer.service]),
):
    results = await usecase.list_classroom_materials(
        classroom_id=classroom_id,
        current_user=current_user,
    )
    return ClassroomMaterialListResponse(
        data=[_build_classroom_material_payload(result) for result in results]
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
    usecase: ClassroomUseCase = Depends(Provide[ClassroomContainer.service]),
):
    result = await usecase.get_classroom_material(
        classroom_id=classroom_id,
        material_id=material_id,
        current_user=current_user,
    )
    return ClassroomMaterialResponse(
        data=_build_classroom_material_payload(result)
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
    usecase: ClassroomUseCase = Depends(Provide[ClassroomContainer.service]),
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
    source_kind: ClassroomMaterialSourceKind | None = Form(None),
    source_url: str | None = Form(None),
    uploaded_file: UploadFile | None = File(None),
    current_user: CurrentUser = Depends(get_current_user),
    usecase: ClassroomUseCase = Depends(Provide[ClassroomContainer.service]),
):
    request_data = {
        key: value
        for key, value in {
            "title": title,
            "week": week,
            "description": description,
            "source_kind": source_kind,
            "source_url": source_url,
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
        raise RequestValidationError([
            {
                "type": "value_error",
                "loc": ("body",),
                "msg": "최소 하나 이상의 수정 필드가 필요합니다.",
                "input": None,
            }
        ])

    if (
        source_kind is ClassroomMaterialSourceKind.LINK
        and uploaded_file is not None
    ):
        raise RequestValidationError([
            {
                "type": "value_error",
                "loc": ("body", "uploaded_file"),
                "msg": "링크 자료에는 uploaded_file을 함께 보낼 수 없습니다.",
                "input": uploaded_file.filename,
            }
        ])
    if (
        uploaded_file is not None
        and source_kind is None
        and request is not None
    ):
        raise RequestValidationError([
            {
                "type": "value_error",
                "loc": ("body", "uploaded_file"),
                "msg": (
                    "uploaded_file 수정 시 source_kind=file을 함께 "
                    "지정해야 합니다."
                ),
                "input": uploaded_file.filename,
            }
        ])
    if (
        source_kind is ClassroomMaterialSourceKind.FILE
        and uploaded_file is None
    ):
        raise RequestValidationError([
            {
                "type": "value_error",
                "loc": ("body", "uploaded_file"),
                "msg": "파일 자료로 변경 시 uploaded_file이 필요합니다.",
                "input": None,
            }
        ])

    result = await usecase.update_classroom_material(
        classroom_id=classroom_id,
        material_id=material_id,
        current_user=current_user,
        command=UpdateClassroomMaterialCommand(
            **(request.model_dump(exclude_unset=True) if request else {})
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
        data=_build_classroom_material_payload(result)
    )


@router.post(
    "/{material_id}/reingest",
    response_model=ClassroomMaterialResponse,
    dependencies=[Depends(PermissionDependency([IsProfessorOrAdmin]))],
)
@inject
async def reingest_classroom_material(
    classroom_id: UUID,
    material_id: UUID,
    current_user: CurrentUser = Depends(get_current_user),
    usecase: ClassroomUseCase = Depends(Provide[ClassroomContainer.service]),
):
    result = await usecase.reingest_classroom_material(
        classroom_id=classroom_id,
        material_id=material_id,
        current_user=current_user,
    )
    return ClassroomMaterialResponse(
        data=_build_classroom_material_payload(result)
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
    usecase: ClassroomUseCase = Depends(Provide[ClassroomContainer.service]),
):
    result = await usecase.delete_classroom_material(
        classroom_id=classroom_id,
        material_id=material_id,
        current_user=current_user,
    )
    return ClassroomMaterialResponse(
        data=_build_classroom_material_payload(result)
    )
