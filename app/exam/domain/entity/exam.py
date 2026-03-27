from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from uuid import UUID

from core.common.entity import AggregateRoot, Entity


class ExamType(StrEnum):
    QUIZ = "quiz"
    MIDTERM = "midterm"
    FINAL = "final"
    MOCK = "mock"


class ExamStatus(StrEnum):
    READY = "ready"
    IN_PROGRESS = "in_progress"
    CLOSED = "closed"


class ExamSessionStatus(StrEnum):
    READY = "ready"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    EXPIRED = "expired"
    CANCELLED = "cancelled"


class ExamTurnRole(StrEnum):
    STUDENT = "student"
    ASSISTANT = "assistant"
    SYSTEM = "system"


class ExamTurnEventType(StrEnum):
    MESSAGE = "message"
    TRANSCRIPT = "transcript"
    SESSION_STARTED = "session_started"
    SESSION_COMPLETED = "session_completed"


class ExamResultStatus(StrEnum):
    PENDING = "pending"
    COMPLETED = "completed"


@dataclass
class ExamCriterion(Entity):
    exam_id: UUID
    title: str
    description: str | None
    weight: int
    sort_order: int
    excellent_definition: str | None = None
    average_definition: str | None = None
    poor_definition: str | None = None


@dataclass
class Exam(AggregateRoot):
    classroom_id: UUID
    title: str
    exam_type: ExamType
    duration_minutes: int
    starts_at: datetime
    ends_at: datetime
    allow_retake: bool
    description: str | None = None
    status: ExamStatus = ExamStatus.READY
    criteria: list[ExamCriterion] = field(default_factory=list)


@dataclass
class ExamSession(Entity):
    exam_id: UUID
    student_id: UUID
    status: ExamSessionStatus
    started_at: datetime
    last_activity_at: datetime
    attempt_number: int
    ended_at: datetime | None = None
    expires_at: datetime | None = None
    provider_session_id: str | None = None


@dataclass
class ExamTurn(Entity):
    session_id: UUID
    sequence: int
    role: ExamTurnRole
    event_type: ExamTurnEventType
    content: str
    created_at: datetime
    metadata: dict[str, str] = field(default_factory=dict)


@dataclass
class ExamResultCriterion(Entity):
    criterion_id: UUID
    score: float | None
    feedback: str | None


@dataclass
class ExamResult(Entity):
    exam_id: UUID
    session_id: UUID
    student_id: UUID
    status: ExamResultStatus
    submitted_at: datetime | None = None
    overall_score: float | None = None
    summary: str | None = None
    strengths: list[str] = field(default_factory=list)
    weaknesses: list[str] = field(default_factory=list)
    improvement_suggestions: list[str] = field(default_factory=list)
    criteria_results: list[ExamResultCriterion] = field(default_factory=list)


@dataclass(frozen=True)
class RealtimeClientSecret:
    value: str
    expires_at: datetime | None = None
    provider_session_id: str | None = None


@dataclass(frozen=True)
class StartedExamSession:
    session: ExamSession
    client_secret: str
