from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field, model_validator

from app.exam.domain.constants import (
    MAX_BLOOM_LEVEL_QUESTION_COUNT,
    MAX_QUESTION_TYPE_QUESTION_COUNT,
)
from app.exam.domain.entity import (
    BloomLevel,
    ExamDifficulty,
    ExamQuestionType,
    ExamQuestionTypeStrategy,
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
    max_attempts: int = Field(..., ge=1, le=10)
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
    max_score: float = Field(..., gt=0)
    question_type: ExamQuestionType = ExamQuestionType.NONE
    bloom_level: BloomLevel
    difficulty: ExamDifficulty
    question_text: str = Field(..., min_length=1, max_length=5000)
    intent_text: str = Field(..., min_length=1, max_length=5000)
    rubric_text: str | None = Field(None, max_length=12000)
    answer_options: list[str] = Field(default_factory=list)
    correct_answer_text: str | None = Field(None, max_length=2000)
    source_material_ids: list[UUID] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_question_payload(self):
        rubric_text = (self.rubric_text or "").strip()
        correct_answer_text = (self.correct_answer_text or "").strip()
        normalized_answer_options = [
            option.strip() for option in self.answer_options if option.strip()
        ]
        if self.question_type is ExamQuestionType.ORAL and not rubric_text:
            raise ValueError("oral rubric_text is required")
        if (
            self.question_type is ExamQuestionType.SUBJECTIVE
            and not correct_answer_text
        ):
            raise ValueError("subjective correct_answer_text is required")
        if self.question_type is not ExamQuestionType.MULTIPLE_CHOICE:
            return self
        if len(normalized_answer_options) < 2:
            raise ValueError(
                "multiple_choice answer_options must contain at least two items"
            )
        if not correct_answer_text:
            raise ValueError("multiple_choice correct_answer_text is required")
        if correct_answer_text not in normalized_answer_options:
            raise ValueError(
                "correct_answer_text must match one of answer_options"
            )
        return self


class UpdateExamQuestionCommand(BaseModel):
    question_number: int | None = Field(None, ge=1, le=500)
    max_score: float | None = Field(None, gt=0)
    question_type: ExamQuestionType | None = None
    bloom_level: BloomLevel | None = None
    difficulty: ExamDifficulty | None = None
    question_text: str | None = Field(None, min_length=1, max_length=5000)
    intent_text: str | None = Field(None, min_length=1, max_length=5000)
    rubric_text: str | None = Field(None, max_length=12000)
    answer_options: list[str] | None = None
    correct_answer_text: str | None = Field(None, max_length=2000)
    source_material_ids: list[UUID] | None = None

    @model_validator(mode="after")
    def validate_non_empty_update(self):
        if not self.model_fields_set:
            raise ValueError("at least one field must be updated")
        return self

    @model_validator(mode="after")
    def validate_question_payload(self):
        rubric_text = (self.rubric_text or "").strip()
        correct_answer_text = (self.correct_answer_text or "").strip()
        normalized_answer_options = [
            option.strip()
            for option in (self.answer_options or [])
            if option.strip()
        ]
        if self.question_type is ExamQuestionType.ORAL and not rubric_text:
            raise ValueError("oral rubric_text is required")
        if (
            self.question_type is ExamQuestionType.SUBJECTIVE
            and not correct_answer_text
        ):
            raise ValueError("subjective correct_answer_text is required")
        if self.question_type is not ExamQuestionType.MULTIPLE_CHOICE:
            return self
        if len(normalized_answer_options) < 2:
            raise ValueError(
                "multiple_choice answer_options must contain at least two items"
            )
        if not correct_answer_text:
            raise ValueError("multiple_choice correct_answer_text is required")
        if correct_answer_text not in normalized_answer_options:
            raise ValueError(
                "correct_answer_text must match one of answer_options"
            )
        return self


class ExamQuestionBloomCountCommand(BaseModel):
    bloom_level: BloomLevel
    count: int = Field(..., ge=1, le=MAX_BLOOM_LEVEL_QUESTION_COUNT)


class ExamQuestionTypeCountCommand(BaseModel):
    question_type: ExamQuestionType
    count: int = Field(..., ge=1, le=MAX_QUESTION_TYPE_QUESTION_COUNT)

    @model_validator(mode="after")
    def validate_question_type(self):
        if self.question_type is ExamQuestionType.NONE:
            raise ValueError("question_type must not be none")
        return self


class GenerateExamQuestionsCommand(BaseModel):
    scope_text: str = Field(..., min_length=1, max_length=1000)
    max_follow_ups: int = Field(..., ge=0, le=20)
    difficulty: ExamDifficulty
    source_material_ids: list[UUID] = Field(default_factory=list)
    bloom_counts: list[ExamQuestionBloomCountCommand] = Field(
        ..., min_length=1, max_length=6
    )
    question_type_counts: list[ExamQuestionTypeCountCommand] | None = Field(
        default=None, min_length=1, max_length=3
    )
    total_question_count: int | None = Field(
        default=None, ge=1, le=MAX_QUESTION_TYPE_QUESTION_COUNT
    )
    question_type_strategy: ExamQuestionTypeStrategy | None = None

    @model_validator(mode="after")
    def validate_distribution_counts(self):
        bloom_levels = [item.bloom_level for item in self.bloom_counts]
        if len(set(bloom_levels)) != len(bloom_levels):
            raise ValueError("bloom levels must not contain duplicates")

        has_legacy_counts = self.question_type_counts is not None
        has_strategy = self.question_type_strategy is not None
        has_total_question_count = self.total_question_count is not None

        if has_legacy_counts and (has_strategy or has_total_question_count):
            raise ValueError(
                "question_type_counts cannot be combined with "
                "question_type_strategy or total_question_count"
            )
        if has_strategy != has_total_question_count:
            raise ValueError(
                "question_type_strategy and total_question_count must be "
                "provided together"
            )
        if not has_legacy_counts and not has_strategy:
            raise ValueError(
                "either question_type_counts or "
                "question_type_strategy/total_question_count must be provided"
            )

        bloom_total = sum(item.count for item in self.bloom_counts)

        if has_legacy_counts:
            assert self.question_type_counts is not None
            question_types = [
                item.question_type for item in self.question_type_counts
            ]
            if len(set(question_types)) != len(question_types):
                raise ValueError("question types must not contain duplicates")
            if bloom_total != sum(
                item.count for item in self.question_type_counts
            ):
                raise ValueError(
                    "bloom counts and question type counts must sum to the "
                    "same total"
                )
            return self

        assert self.total_question_count is not None
        if bloom_total != self.total_question_count:
            raise ValueError(
                "bloom counts and total_question_count must sum to the "
                "same total"
            )
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
    occurred_at: datetime
