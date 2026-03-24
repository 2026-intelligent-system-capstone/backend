from pydantic import Field, model_validator

from app.file.domain.entity.file import FileStatus
from core.common.request.base import BaseRequest


class CreateFileRequest(BaseRequest):
    file_name: str = Field(..., min_length=1, max_length=255)
    file_path: str = Field(..., min_length=1, max_length=512)
    file_extension: str = Field(..., min_length=1, max_length=10)
    file_size: int = Field(..., gt=0)
    mime_type: str = Field(..., min_length=1, max_length=100)


class UpdateFileRequest(BaseRequest):
    file_name: str | None = Field(None, min_length=1, max_length=255)
    file_path: str | None = Field(None, min_length=1, max_length=512)
    file_extension: str | None = Field(None, min_length=1, max_length=10)
    file_size: int | None = Field(None, gt=0)
    mime_type: str | None = Field(None, min_length=1, max_length=100)
    status: FileStatus | None = None

    @model_validator(mode="after")
    def validate_non_empty_update(self):
        if not any(value is not None for value in self.model_dump().values()):
            raise ValueError("최소 하나 이상의 수정 필드가 필요합니다.")
        return self
