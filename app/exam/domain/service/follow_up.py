from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from uuid import UUID

from app.exam.domain.entity import (
    BloomLevel,
    ExamDifficulty,
    ExamQuestionType,
    ExamTurnEventType,
    ExamTurnRole,
)


@dataclass(frozen=True)
class ExamFollowUpGenerationQuestion:
    question_id: UUID
    question_number: int
    question_type: ExamQuestionType
    bloom_level: BloomLevel
    difficulty: ExamDifficulty
    question_text: str
    intent_text: str
    rubric_text: str
    max_follow_ups: int
    source_material_ids: list[UUID] = field(default_factory=list)


@dataclass(frozen=True)
class ExamFollowUpGenerationTurn:
    sequence: int
    role: ExamTurnRole
    event_type: ExamTurnEventType
    content: str
    metadata: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class ExamFollowUpGenerationRequest:
    exam_id: UUID
    session_id: UUID
    student_id: UUID
    exam_title: str
    question: ExamFollowUpGenerationQuestion
    answer_content: str
    turns: list[ExamFollowUpGenerationTurn] = field(default_factory=list)
    metadata: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class ExamFollowUpGenerationResult:
    content: str
    event_type: ExamTurnEventType = ExamTurnEventType.FOLLOW_UP
    metadata: dict[str, str] = field(default_factory=dict)


class ExamFollowUpGenerationPort(ABC):
    @abstractmethod
    async def generate_follow_up(
        self,
        *,
        request: ExamFollowUpGenerationRequest,
    ) -> ExamFollowUpGenerationResult:
        """Generate one assistant follow-up question."""
