from datetime import datetime
from uuid import UUID

from pydantic import Field, model_validator

from app.exam.domain.constants import MAX_QUESTION_TYPE_QUESTION_COUNT
from app.exam.domain.entity import (
    BloomLevel,
    ExamDifficulty,
    ExamQuestionType,
    ExamQuestionTypeStrategy,
    ExamTurnEventType,
    ExamTurnRole,
    ExamType,
)
from core.common.request.base import BaseRequest


class ExamCriterionRequest(BaseRequest):
    null_fields = {
        "description",
        "excellent_definition",
        "average_definition",
        "poor_definition",
    }

    title: str = Field(..., min_length=1, max_length=100)
    description: str | None = Field(None, max_length=1000)
    weight: int = Field(..., ge=1, le=100)
    sort_order: int = Field(..., ge=1)
    excellent_definition: str | None = Field(None, max_length=1000)
    average_definition: str | None = Field(None, max_length=1000)
    poor_definition: str | None = Field(None, max_length=1000)


class CreateExamRequest(BaseRequest):
    null_fields = {"description"}

    title: str = Field(..., min_length=2, max_length=100)
    description: str | None = Field(None, max_length=1000)
    exam_type: ExamType
    duration_minutes: int = Field(..., ge=1, le=600)
    starts_at: datetime
    ends_at: datetime
    max_attempts: int = Field(..., ge=1, le=10)
    week: int = Field(..., ge=1)
    question_count: int = Field(..., ge=1, le=MAX_QUESTION_TYPE_QUESTION_COUNT)
    difficulty: ExamDifficulty
    criteria: list[ExamCriterionRequest] = Field(
        ..., min_length=1, max_length=20
    )

    @model_validator(mode="after")
    def validate_exam_rules(self):
        if self.starts_at >= self.ends_at:
            raise ValueError("starts_at must be before ends_at")
        if sum(criterion.weight for criterion in self.criteria) != 100:
            raise ValueError("criteria weights must sum to 100")
        return self


class ExamQuestionAnswerOptionPayload(BaseRequest):
    id: str = Field(..., min_length=1, max_length=100)
    label: str = Field(..., min_length=1, max_length=20)
    text: str = Field(..., min_length=1, max_length=2000)
    is_correct: bool = False
    explanation: str | None = Field(None, max_length=2000)


class ExamQuestionAnswerKeyPayload(BaseRequest):
    type: ExamQuestionType
    correct_option_ids: list[str] = Field(default_factory=list)
    model_answer: str | None = Field(None, max_length=5000)
    acceptable_answers: list[str] = Field(default_factory=list)
    required_keywords: list[str] = Field(default_factory=list)
    expected_points: list[str] = Field(default_factory=list)
    follow_up_questions: list[str] = Field(default_factory=list)


class ExamQuestionRubricCriterionPayload(BaseRequest):
    name: str = Field(..., min_length=1, max_length=100)
    description: str = Field(..., min_length=1, max_length=2000)
    points: float = Field(..., gt=0)


class ExamQuestionRubricPayload(BaseRequest):
    criteria: list[ExamQuestionRubricCriterionPayload] = Field(
        default_factory=list
    )
    evidence_policy: str | None = Field(None, max_length=5000)


class UpdateExamQuestionRequest(BaseRequest):
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
    answer_options_data: list[ExamQuestionAnswerOptionPayload] | None = None
    answer_key_data: ExamQuestionAnswerKeyPayload | None = None
    rubric_data: ExamQuestionRubricPayload | None = None
    source_material_ids: list[UUID] | None = None

    @model_validator(mode="after")
    def validate_non_empty_update(self):
        if not self.model_fields_set:
            raise ValueError("최소 하나 이상의 수정 필드가 필요합니다.")
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
        has_structured_answer_key = self.answer_key_data is not None
        has_structured_rubric = self.rubric_data is not None
        if (
            self.question_type is ExamQuestionType.ORAL
            and not rubric_text
            and not has_structured_answer_key
            and not has_structured_rubric
        ):
            raise ValueError("구술형은 루브릭(rubric_text)을 입력해야 합니다.")
        if (
            self.question_type is ExamQuestionType.SUBJECTIVE
            and not correct_answer_text
            and not has_structured_answer_key
        ):
            raise ValueError(
                "주관식은 정답(correct_answer_text)을 입력해야 합니다."
            )
        if self.question_type is not ExamQuestionType.MULTIPLE_CHOICE:
            return self
        has_structured_multiple_choice = (
            bool(self.answer_options_data) and self.answer_key_data is not None
        )
        if has_structured_multiple_choice:
            return self
        if len(normalized_answer_options) < 2:
            raise ValueError(
                "객관식은 보기(answer_options)를 두 개 이상 입력해야 합니다."
            )
        if not correct_answer_text:
            raise ValueError(
                "객관식은 정답(correct_answer_text)을 입력해야 합니다."
            )
        if correct_answer_text not in normalized_answer_options:
            raise ValueError(
                "객관식 정답은 answer_options 중 하나와 정확히 일치해야 합니다."
            )
        return self


class ExamQuestionBloomWeightRequest(BaseRequest):
    bloom_level: BloomLevel
    weight: int = Field(..., ge=0, le=10)


class ExamQuestionTypeCountRequest(BaseRequest):
    question_type: ExamQuestionType
    count: int = Field(..., ge=1, le=MAX_QUESTION_TYPE_QUESTION_COUNT)

    @model_validator(mode="after")
    def validate_question_type(self):
        if self.question_type is ExamQuestionType.NONE:
            raise ValueError("문제 유형은 none일 수 없습니다.")
        return self


class GenerateExamQuestionsRequest(BaseRequest):
    scope_text: str = Field(..., min_length=1, max_length=1000)
    max_follow_ups: int = Field(..., ge=0, le=20)
    source_material_ids: list[UUID] = Field(default_factory=list)
    bloom_weights: list[ExamQuestionBloomWeightRequest] = Field(
        ..., min_length=1, max_length=6
    )
    question_type_counts: list[ExamQuestionTypeCountRequest] | None = Field(
        default=None, min_length=1, max_length=3
    )
    question_type_strategy: ExamQuestionTypeStrategy | None = None

    @model_validator(mode="after")
    def validate_distribution_counts(self):
        bloom_levels = [item.bloom_level for item in self.bloom_weights]
        if len(set(bloom_levels)) != len(bloom_levels):
            raise ValueError("Bloom 단계는 중복될 수 없습니다.")
        if sum(item.weight for item in self.bloom_weights) <= 0:
            raise ValueError(
                "Bloom 단계별 가중치 중 하나 이상은 0보다 커야 합니다."
            )

        has_legacy_counts = self.question_type_counts is not None
        has_strategy = self.question_type_strategy is not None

        if has_legacy_counts and has_strategy:
            raise ValueError(
                "문제 유형별 개수와 문제 유형 전략은 함께 보낼 수 없습니다."
            )
        if not has_legacy_counts and not has_strategy:
            raise ValueError(
                "문제 유형별 개수 또는 문제 유형 전략 중 하나는 "
                "반드시 필요합니다."
            )
        if has_legacy_counts:
            assert self.question_type_counts is not None
            question_types = [
                item.question_type for item in self.question_type_counts
            ]
            if len(set(question_types)) != len(question_types):
                raise ValueError("문제 유형은 중복될 수 없습니다.")
        return self


class RecordExamTurnRequest(BaseRequest):
    role: ExamTurnRole
    event_type: ExamTurnEventType
    content: str = Field(..., min_length=1, max_length=10000)
    metadata: dict[str, str] = Field(default_factory=dict)
    occurred_at: datetime


class GenerateExamFollowUpRequest(BaseRequest):
    question_id: UUID
    answer_content: str = Field(..., min_length=1, max_length=10000)
    metadata: dict[str, str] = Field(default_factory=dict)
    occurred_at: datetime


class CompleteExamSessionRequest(BaseRequest):
    occurred_at: datetime


class FinalizeExamResultRequest(BaseRequest):
    occurred_at: datetime
