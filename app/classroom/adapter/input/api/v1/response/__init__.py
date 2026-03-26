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
