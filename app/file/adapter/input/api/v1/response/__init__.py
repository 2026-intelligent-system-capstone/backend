from pydantic import BaseModel, Field

from app.file.domain.entity.file import FileStatus
from core.common.response.base import BaseResponse


class FilePayload(BaseModel):
    id: str
    file_name: str
    file_path: str
    file_extension: str
    file_size: int
    mime_type: str
    status: FileStatus


class FileResponse(BaseResponse):
    data: FilePayload = Field(...)


class FileListResponse(BaseResponse):
    data: list[FilePayload] = Field(...)
