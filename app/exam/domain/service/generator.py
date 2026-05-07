from abc import ABC, abstractmethod
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import datetime
from uuid import UUID

from app.async_job.domain.entity import AsyncJobReference
from app.exam.domain.constants import MAX_QUESTION_TYPE_QUESTION_COUNT
from app.exam.domain.entity import (
    BloomLevel,
    ExamDifficulty,
    ExamGenerationStatus,
    ExamQuestionAnswerKey,
    ExamQuestionAnswerOption,
    ExamQuestionRubric,
    ExamQuestionType,
    ExamType,
)


@dataclass(frozen=True)
class ExamQuestionGenerationCriterion:
    title: str
    description: str | None
    weight: int
    excellent_definition: str | None = None
    average_definition: str | None = None
    poor_definition: str | None = None


@dataclass(frozen=True)
class ExamQuestionGenerationLevelCount:
    bloom_level: BloomLevel
    count: int

    def __post_init__(self) -> None:
        if self.count < 0 or self.count > MAX_QUESTION_TYPE_QUESTION_COUNT:
            raise ValueError("count must be between 0 and 30")


@dataclass(frozen=True)
class ExamQuestionGenerationLevelWeight:
    bloom_level: BloomLevel
    weight: int

    def __post_init__(self) -> None:
        if self.weight < 0 or self.weight > 10:
            raise ValueError("weight must be between 0 and 10")


def allocate_bloom_weight_counts(
    *,
    total_question_count: int,
    weights: Sequence[ExamQuestionGenerationLevelWeight],
) -> list[ExamQuestionGenerationLevelCount]:
    if (
        total_question_count < 1
        or total_question_count > MAX_QUESTION_TYPE_QUESTION_COUNT
    ):
        raise ValueError("total_question_count must be between 1 and 30")
    if not weights:
        raise ValueError("weights must not be empty")

    bloom_levels = [item.bloom_level for item in weights]
    if len(set(bloom_levels)) != len(bloom_levels):
        raise ValueError("bloom levels must not contain duplicates")

    total_weight = sum(item.weight for item in weights)
    if total_weight <= 0:
        raise ValueError("total weight must be greater than 0")

    positive_weights = [item for item in weights if item.weight > 0]
    allocated_counts = [
        (total_question_count * item.weight) // total_weight
        for item in positive_weights
    ]
    remaining_count = total_question_count - sum(allocated_counts)
    remainders = [
        (total_question_count * item.weight) % total_weight
        for item in positive_weights
    ]
    remainder_order = sorted(
        range(len(positive_weights)),
        key=lambda index: (-remainders[index], index),
    )

    for index in remainder_order[:remaining_count]:
        allocated_counts[index] += 1

    return [
        ExamQuestionGenerationLevelCount(
            bloom_level=item.bloom_level,
            count=allocated_counts[index],
        )
        for index, item in enumerate(positive_weights)
        if allocated_counts[index] > 0
    ]


@dataclass(frozen=True)
class ExamQuestionGenerationTypeCount:
    question_type: ExamQuestionType
    count: int

    def __post_init__(self) -> None:
        if self.question_type is ExamQuestionType.NONE:
            raise ValueError("question_type must not be none")
        if self.count < 1 or self.count > MAX_QUESTION_TYPE_QUESTION_COUNT:
            raise ValueError("count must be between 1 and 30")


@dataclass(frozen=True)
class ExamQuestionSourceMaterial:
    material_id: UUID
    file_name: str
    title: str
    week: int


@dataclass(frozen=True)
class GeneratedExamQuestionDraft:
    question_number: int
    max_score: float
    question_type: ExamQuestionType
    bloom_level: BloomLevel
    difficulty: ExamDifficulty
    question_text: str
    intent_text: str
    rubric_text: str
    answer_options: list[str] = field(default_factory=list)
    correct_answer_text: str | None = None
    answer_options_data: list[ExamQuestionAnswerOption] = field(
        default_factory=list
    )
    answer_key_data: ExamQuestionAnswerKey | None = None
    rubric_data: ExamQuestionRubric = field(default_factory=ExamQuestionRubric)
    source_material_ids: list[UUID] = field(default_factory=list)

    def __post_init__(self) -> None:
        if self.max_score <= 0:
            raise ValueError("max_score must be greater than 0")


@dataclass(frozen=True)
class ExamQuestionGenerationSubmitResult:
    exam_id: UUID
    generation_status: ExamGenerationStatus
    job: AsyncJobReference
    generation_requested_at: datetime | None = None
    generation_error: str | None = None


@dataclass(frozen=True)
class GenerateExamQuestionsRequest:
    exam_id: UUID
    classroom_id: UUID
    title: str
    exam_type: ExamType
    scope_text: str
    max_follow_ups: int
    difficulty: ExamDifficulty
    criteria: list[ExamQuestionGenerationCriterion] = field(
        default_factory=list
    )
    bloom_counts: list[ExamQuestionGenerationLevelCount] = field(
        default_factory=list
    )
    question_type_counts: list[ExamQuestionGenerationTypeCount] = field(
        default_factory=list
    )
    source_materials: list[ExamQuestionSourceMaterial] = field(
        default_factory=list
    )

    def __post_init__(self) -> None:
        if self.total_questions != sum(
            item.count for item in self.question_type_counts
        ):
            raise ValueError(
                "bloom_counts and question_type_counts must have the same total"
            )

    @property
    def total_questions(self) -> int:
        return sum(item.count for item in self.bloom_counts)


class ExamQuestionGenerationPort(ABC):
    @abstractmethod
    async def generate_questions(
        self,
        *,
        request: GenerateExamQuestionsRequest,
    ) -> Sequence[GeneratedExamQuestionDraft]:
        """Generate draft questions for one exam."""
