from abc import ABC, abstractmethod
from collections.abc import Sequence
from dataclasses import dataclass, field
from uuid import UUID

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
class ExamQuestionGenerationRatio:
    bloom_level: BloomLevel
    percentage: int


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
    total_questions: int
    max_follow_ups: int
    difficulty: ExamDifficulty
    criteria: list[ExamQuestionGenerationCriterion] = field(
        default_factory=list
    )
    bloom_ratios: list[ExamQuestionGenerationRatio] = field(
        default_factory=list
    )
    source_materials: list[ExamQuestionSourceMaterial] = field(
        default_factory=list
    )


class ExamQuestionGenerationPort(ABC):
    @abstractmethod
    async def generate_questions(
        self,
        *,
        request: GenerateExamQuestionsRequest,
    ) -> Sequence[GeneratedExamQuestionDraft]:
        """Generate draft questions for one exam."""
