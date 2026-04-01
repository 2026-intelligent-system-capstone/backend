from datetime import datetime

from pydantic import BaseModel, Field

from core.common.response.base import BaseResponse


class ClassroomPayload(BaseModel):
    id: str
    name: str
    professor_ids: list[str]
    grade: int
    semester: str
    section: str
    description: str | None = None
    student_ids: list[str]
    allow_student_material_access: bool


class ClassroomResponse(BaseResponse):
    data: ClassroomPayload = Field(default=...)


class ClassroomListResponse(BaseResponse):
    data: list[ClassroomPayload] = Field(default=...)


class ClassroomMaterialFilePayload(BaseModel):
    id: str
    file_name: str
    file_path: str
    file_extension: str
    file_size: int
    mime_type: str


class ClassroomMaterialScopeCandidatePayload(BaseModel):
    label: str
    scope_text: str
    keywords: list[str] = Field(default_factory=list)
    week_range: str | None = None
    confidence: float | None = None


class ClassroomMaterialPayload(BaseModel):
    id: str
    classroom_id: str
    title: str
    week: int
    description: str | None = None
    uploaded_by: str
    uploaded_at: datetime | None = None
    ingest_status: str
    ingest_error: str | None = None
    scope_candidates: list[ClassroomMaterialScopeCandidatePayload] = Field(
        default_factory=list
    )
    file: ClassroomMaterialFilePayload


class ClassroomMaterialResponse(BaseResponse):
    data: ClassroomMaterialPayload = Field(default=...)


class ClassroomMaterialListResponse(BaseResponse):
    data: list[ClassroomMaterialPayload] = Field(default=...)
