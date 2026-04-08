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


class ExamQuestionPayload(BaseModel):
    id: str
    exam_id: str
    question_number: int
    bloom_level: str
    difficulty: str
    question_text: str
    scope_text: str
    evaluation_objective: str
    answer_key: str
    scoring_criteria: str
    source_material_ids: list[str]
    status: str


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
    max_attempts: int
    week: int
    criteria: list[ExamCriterionPayload]
    questions: list[ExamQuestionPayload] = Field(default_factory=list)


class ExamResponse(BaseResponse):
    data: ExamPayload = Field(default=...)


class ExamListResponse(BaseResponse):
    data: list[ExamPayload] = Field(default=...)


class ExamQuestionResponse(BaseResponse):
    data: ExamQuestionPayload = Field(default=...)


class ExamQuestionListResponse(BaseResponse):
    data: list[ExamQuestionPayload] = Field(default=...)


class ExamSessionPayload(BaseModel):
    session_id: str
    exam_id: str
    student_id: str
    status: str
    started_at: str
    ended_at: str | None = None
    expires_at: str | None
    client_secret: str | None = None


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


class ExamResultResponse(BaseResponse):
    data: ExamResultPayload = Field(default=...)


class ExamTurnPayload(BaseModel):
    id: str
    session_id: str
    sequence: int
    role: str
    event_type: str
    content: str
    created_at: str
    metadata: dict[str, str]


class ExamTurnResponse(BaseResponse):
    data: ExamTurnPayload = Field(default=...)
