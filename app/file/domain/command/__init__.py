from pydantic import BaseModel

from app.file.domain.entity.file import FileStatus


class CreateFileCommand(BaseModel):
    file_name: str
    file_path: str
    file_extension: str
    file_size: int
    mime_type: str


class UpdateFileCommand(BaseModel):
    file_name: str | None = None
    file_path: str | None = None
    file_extension: str | None = None
    file_size: int | None = None
    mime_type: str | None = None
    status: FileStatus | None = None
