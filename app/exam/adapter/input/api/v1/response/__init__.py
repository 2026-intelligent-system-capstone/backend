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
    max_score: float
    question_type: str
    bloom_level: str
    difficulty: str
    question_text: str
    intent_text: str
    rubric_text: str
    answer_options: list[str] = Field(default_factory=list)
    correct_answer_text: str | None = None
    source_material_ids: list[str]
    status: str


class ExamPayload(BaseModel):
    id: str
    classroom_id: str
    title: str
    description: str | None = None
    exam_type: str
    status: str
    generation_status: str
    generation_error: str | None = None
    generation_job_id: str | None = None
    generation_requested_at: str | None = None
    generation_completed_at: str | None = None
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


class ExamQuestionGenerationSubmitPayload(BaseModel):
    exam_id: str
    generation_status: str
    job_id: str
    job_status: str
    generation_requested_at: str | None = None
    generation_error: str | None = None


class ExamQuestionGenerationSubmitResponse(BaseResponse):
    data: ExamQuestionGenerationSubmitPayload = Field(default=...)


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


class ExamResultCriterionPayload(BaseModel):
    criterion_id: str
    score: float | None = None
    feedback: str | None = None


class ExamResultPayload(BaseModel):
    id: str
    exam_id: str
    session_id: str
    student_id: str
    status: str
    submitted_at: str | None = None
    overall_score: float | None = None
    summary: str | None = None
    strengths: list[str] = Field(default_factory=list)
    weaknesses: list[str] = Field(default_factory=list)
    improvement_suggestions: list[str] = Field(default_factory=list)
    criteria_results: list[ExamResultCriterionPayload] = Field(
        default_factory=list
    )


class ExamResultListResponse(BaseResponse):
    data: list[ExamResultPayload] = Field(default=...)


class ExamResultResponse(BaseResponse):
    data: ExamResultPayload = Field(default=...)


class StudentExamPayload(ExamPayload):
    is_completed: bool
    can_enter: bool
    latest_result: ExamResultPayload | None = None


class StudentExamResponse(BaseResponse):
    data: StudentExamPayload = Field(default=...)


class StudentExamListResponse(BaseResponse):
    data: list[StudentExamPayload] = Field(default=...)


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
