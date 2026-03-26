from datetime import datetime

from pydantic import BaseModel, Field, model_validator

from app.exam.domain.entity import ExamTurnEventType, ExamTurnRole, ExamType


class ExamCriterionCommand(BaseModel):
    title: str = Field(..., min_length=1, max_length=100)
    description: str | None = Field(None, max_length=1000)
    weight: int = Field(..., ge=1, le=100)
    sort_order: int = Field(..., ge=1)
    excellent_definition: str | None = Field(None, max_length=1000)
    average_definition: str | None = Field(None, max_length=1000)
    poor_definition: str | None = Field(None, max_length=1000)


class CreateExamCommand(BaseModel):
    title: str = Field(..., min_length=2, max_length=100)
    description: str | None = Field(None, max_length=1000)
    exam_type: ExamType
    duration_minutes: int = Field(..., ge=1, le=600)
    starts_at: datetime
    ends_at: datetime
    allow_retake: bool = False
    criteria: list[ExamCriterionCommand] = Field(
        ..., min_length=1, max_length=20
    )

    @model_validator(mode="after")
    def validate_exam_rules(self):
        if self.starts_at >= self.ends_at:
            raise ValueError("starts_at must be before ends_at")
        if sum(criterion.weight for criterion in self.criteria) != 100:
            raise ValueError("criteria weights must sum to 100")
        return self


class RecordExamTurnCommand(BaseModel):
    role: ExamTurnRole
    event_type: ExamTurnEventType
    content: str = Field(..., min_length=1, max_length=10000)
    metadata: dict[str, str] = Field(default_factory=dict)
    occurred_at: datetime


class CompleteExamSessionCommand(BaseModel):
    occurred_at: datetime


class FinalizeExamResultCommand(BaseModel):
    overall_score: int = Field(..., ge=0, le=100)
    summary: str = Field(..., min_length=1, max_length=2000)
    occurred_at: datetime
