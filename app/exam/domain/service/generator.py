from abc import ABC, abstractmethod
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import datetime
from uuid import UUID

from app.async_job.domain.entity import AsyncJobReference
from app.exam.domain.constants import (
    MAX_BLOOM_LEVEL_QUESTION_COUNT,
    MAX_QUESTION_TYPE_QUESTION_COUNT,
)
from app.exam.domain.entity import (
    BloomLevel,
    ExamDifficulty,
    ExamGenerationStatus,
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
        if self.count < 1 or self.count > MAX_BLOOM_LEVEL_QUESTION_COUNT:
            raise ValueError("count must be between 1 and 5")


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
