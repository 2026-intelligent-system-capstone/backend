from abc import ABC, abstractmethod
from collections.abc import Sequence
from dataclasses import dataclass, field
from uuid import UUID

from app.exam.domain.constants import MAX_BLOOM_LEVEL_QUESTION_COUNT
from app.exam.domain.entity import BloomLevel, ExamDifficulty, ExamType


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
class ExamQuestionSourceMaterial:
    material_id: UUID
    file_name: str
    title: str
    week: int


@dataclass(frozen=True)
class GeneratedExamQuestionDraft:
    question_number: int
    bloom_level: BloomLevel
    difficulty: ExamDifficulty
    question_text: str
    scope_text: str
    evaluation_objective: str
    answer_key: str
    scoring_criteria: str
    source_material_ids: list[UUID] = field(default_factory=list)


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
    source_materials: list[ExamQuestionSourceMaterial] = field(
        default_factory=list
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
