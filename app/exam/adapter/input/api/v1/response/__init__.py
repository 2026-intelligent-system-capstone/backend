from pydantic import BaseModel, Field

from core.common.response.base import BaseResponse


class ExamCriterionPayload(BaseModel):
    id: str
    title: str
    description: str | None = None
    weight: int
    sort_order: int
    excellent_definition: str | None = None
    average_definition: str | None = None
    poor_definition: str | None = None


class ExamPayload(BaseModel):
    id: str
    classroom_id: str
    title: str
    description: str | None = None
    exam_type: str
    status: str
    duration_minutes: int
    starts_at: str
    ends_at: str
    allow_retake: bool
    criteria: list[ExamCriterionPayload]


class ExamResponse(BaseResponse):
    data: ExamPayload = Field(default=...)


class ExamListResponse(BaseResponse):
    data: list[ExamPayload] = Field(default=...)


class ExamSessionPayload(BaseModel):
    session_id: str
    exam_id: str
    student_id: str
    status: str
    started_at: str
    expires_at: str | None
    client_secret: str


class ExamSessionResponse(BaseResponse):
    data: ExamSessionPayload = Field(default=...)


class ExamResultPayload(BaseModel):
    id: str
    exam_id: str
    session_id: str
    student_id: str
    status: str
    submitted_at: str | None = None
    overall_score: int | None = None
    summary: str | None = None


class ExamResultListResponse(BaseResponse):
    data: list[ExamResultPayload] = Field(default=...)
