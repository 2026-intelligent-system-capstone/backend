from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from uuid import UUID

from app.exam.domain.entity import (
    ExamDifficulty,
    ExamQuestionType,
    ExamTurnEventType,
    ExamTurnRole,
    ExamType,
)


@dataclass(frozen=True)
class ExamResultEvaluationCriterion:
    criterion_id: UUID
    title: str
    weight: int
    description: str | None = None
    excellent_definition: str | None = None
    average_definition: str | None = None
    poor_definition: str | None = None


@dataclass(frozen=True)
class ExamResultEvaluationQuestion:
    question_number: int
    max_score: float
    question_type: ExamQuestionType
    difficulty: ExamDifficulty
    question_text: str
    intent_text: str
    rubric_text: str
    answer_options: list[str] = field(default_factory=list)
    correct_answer_text: str | None = None


@dataclass(frozen=True)
class ExamResultEvaluationTurn:
    sequence: int
    role: ExamTurnRole
    event_type: ExamTurnEventType
    content: str
    metadata: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class EvaluateExamResultRequest:
    exam_id: UUID
    session_id: UUID
    student_id: UUID
    exam_title: str
    exam_type: ExamType
    criteria: list[ExamResultEvaluationCriterion] = field(default_factory=list)
    questions: list[ExamResultEvaluationQuestion] = field(default_factory=list)
    turns: list[ExamResultEvaluationTurn] = field(default_factory=list)


@dataclass(frozen=True)
class ExamResultEvaluationCriterionScore:
    criterion_id: UUID
    score: float
    feedback: str


@dataclass(frozen=True)
class EvaluateExamResult:
    summary: str
    strengths: list[str] = field(default_factory=list)
    weaknesses: list[str] = field(default_factory=list)
    improvement_suggestions: list[str] = field(default_factory=list)
    criteria_results: list[ExamResultEvaluationCriterionScore] = field(
        default_factory=list
    )


class ExamResultEvaluationPort(ABC):
    @abstractmethod
    async def evaluate_result(
        self,
        *,
        request: EvaluateExamResultRequest,
    ) -> EvaluateExamResult:
        """Evaluate one completed exam session result."""
