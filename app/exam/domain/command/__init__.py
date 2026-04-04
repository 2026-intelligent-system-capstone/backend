from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field, model_validator

from app.exam.domain.entity import (
    BloomLevel,
    ExamDifficulty,
    ExamTurnEventType,
    ExamTurnRole,
    ExamType,
)


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
    week: int = Field(..., ge=1)
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


class CreateExamQuestionCommand(BaseModel):
    question_number: int = Field(..., ge=1, le=500)
    bloom_level: BloomLevel
    difficulty: ExamDifficulty
    question_text: str = Field(..., min_length=1, max_length=5000)
    scope_text: str = Field(..., min_length=1, max_length=1000)
    evaluation_objective: str = Field(..., min_length=1, max_length=2000)
    answer_key: str = Field(..., min_length=1, max_length=5000)
    scoring_criteria: str = Field(..., min_length=1, max_length=5000)
    source_material_ids: list[UUID] = Field(default_factory=list)


class UpdateExamQuestionCommand(BaseModel):
    question_number: int | None = Field(None, ge=1, le=500)
    bloom_level: BloomLevel | None = None
    difficulty: ExamDifficulty | None = None
    question_text: str | None = Field(None, min_length=1, max_length=5000)
    scope_text: str | None = Field(None, min_length=1, max_length=1000)
    evaluation_objective: str | None = Field(
        None, min_length=1, max_length=2000
    )
    answer_key: str | None = Field(None, min_length=1, max_length=5000)
    scoring_criteria: str | None = Field(
        None, min_length=1, max_length=5000
    )
    source_material_ids: list[UUID] | None = None

    @model_validator(mode="after")
    def validate_non_empty_update(self):
        if not self.model_fields_set:
            raise ValueError("at least one field must be updated")
        return self


class ExamQuestionBloomRatioCommand(BaseModel):
    bloom_level: BloomLevel
    percentage: int = Field(..., ge=1, le=100)


class GenerateExamQuestionsCommand(BaseModel):
    scope_text: str = Field(..., min_length=1, max_length=1000)
    total_questions: int = Field(..., ge=1, le=100)
    max_follow_ups: int = Field(..., ge=0, le=20)
    difficulty: ExamDifficulty
    source_material_ids: list[UUID] = Field(default_factory=list)
    bloom_ratios: list[ExamQuestionBloomRatioCommand] = Field(
        ..., min_length=1, max_length=6
    )

    @model_validator(mode="after")
    def validate_bloom_ratios(self):
        if sum(item.percentage for item in self.bloom_ratios) != 100:
            raise ValueError("bloom ratios must sum to 100")
        bloom_levels = [item.bloom_level for item in self.bloom_ratios]
        if len(set(bloom_levels)) != len(bloom_levels):
            raise ValueError("bloom ratios must not contain duplicates")
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
