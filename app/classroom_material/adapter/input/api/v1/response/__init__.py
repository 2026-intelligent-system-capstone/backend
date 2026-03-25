from datetime import datetime

from pydantic import BaseModel, Field

from core.common.response.base import BaseResponse


class ClassroomMaterialFilePayload(BaseModel):
    id: str
    file_name: str
    file_path: str
    file_extension: str
    file_size: int
    mime_type: str


class ClassroomMaterialPayload(BaseModel):
    id: str
    classroom_id: str
    title: str
    week: int
    description: str | None = None
    uploaded_by: str
    uploaded_at: datetime | None = None
    file: ClassroomMaterialFilePayload


class ClassroomMaterialResponse(BaseResponse):
    data: ClassroomMaterialPayload = Field(default=...)


class ClassroomMaterialListResponse(BaseResponse):
    data: list[ClassroomMaterialPayload] = Field(default=...)
