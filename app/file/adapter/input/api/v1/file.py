from uuid import UUID

from dependency_injector.wiring import Provide, inject
from fastapi import APIRouter, Depends

from app.file.adapter.input.api.v1.request import (
    CreateFileRequest,
    UpdateFileRequest,
)
from app.file.adapter.input.api.v1.response import (
    FileListResponse,
    FilePayload,
    FileResponse,
)
from app.file.container import FileContainer
from app.file.domain.command import CreateFileCommand, UpdateFileCommand
from app.file.domain.usecase.file import FileUseCase

router = APIRouter(prefix="/files", tags=["files"])


@router.post("", response_model=FileResponse)
@inject
async def create_file(
    request: CreateFileRequest,
    usecase: FileUseCase = Depends(Provide[FileContainer.service]),
):
    file = await usecase.create_file(CreateFileCommand(**request.model_dump()))
    return FileResponse(
        data=FilePayload(
            id=str(file.id),
            file_name=file.file_name,
            file_path=file.file_path,
            file_extension=file.file_extension,
            file_size=file.file_size,
            mime_type=file.mime_type,
            status=file.status,
        )
    )


@router.get("", response_model=FileListResponse)
@inject
async def list_files(
    usecase: FileUseCase = Depends(Provide[FileContainer.service]),
):
    files = await usecase.list_files()
    return FileListResponse(
        data=[
            FilePayload(
                id=str(file.id),
                file_name=file.file_name,
                file_path=file.file_path,
                file_extension=file.file_extension,
                file_size=file.file_size,
                mime_type=file.mime_type,
                status=file.status,
            )
            for file in files
        ]
    )


@router.get("/{file_id}", response_model=FileResponse)
@inject
async def get_file(
    file_id: UUID,
    usecase: FileUseCase = Depends(Provide[FileContainer.service]),
):
    file = await usecase.get_file(file_id)
    return FileResponse(
        data=FilePayload(
            id=str(file.id),
            file_name=file.file_name,
            file_path=file.file_path,
            file_extension=file.file_extension,
            file_size=file.file_size,
            mime_type=file.mime_type,
            status=file.status,
        )
    )


@router.patch("/{file_id}", response_model=FileResponse)
@inject
async def update_file(
    file_id: UUID,
    request: UpdateFileRequest,
    usecase: FileUseCase = Depends(Provide[FileContainer.service]),
):
    file = await usecase.update_file(
        file_id,
        UpdateFileCommand(**request.model_dump(exclude_unset=True)),
    )
    return FileResponse(
        data=FilePayload(
            id=str(file.id),
            file_name=file.file_name,
            file_path=file.file_path,
            file_extension=file.file_extension,
            file_size=file.file_size,
            mime_type=file.mime_type,
            status=file.status,
        )
    )


@router.delete("/{file_id}", response_model=FileResponse)
@inject
async def delete_file(
    file_id: UUID,
    usecase: FileUseCase = Depends(Provide[FileContainer.service]),
):
    file = await usecase.delete_file(file_id)
    return FileResponse(
        data=FilePayload(
            id=str(file.id),
            file_name=file.file_name,
            file_path=file.file_path,
            file_extension=file.file_extension,
            file_size=file.file_size,
            mime_type=file.mime_type,
            status=file.status,
        )
    )
