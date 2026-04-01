from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from uuid import UUID

from app.auth.application.exception import AuthForbiddenException
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
    QUESTION = "question"
    ANSWER = "answer"
    FOLLOW_UP = "follow_up"
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

    @classmethod
    def create(
        cls,
        *,
        classroom_id: UUID,
        title: str,
        description: str | None,
        exam_type: ExamType,
        duration_minutes: int,
        starts_at: datetime,
        ends_at: datetime,
        allow_retake: bool,
        criteria: Sequence[ExamCriterion],
    ) -> "Exam":
        exam = cls(
            classroom_id=classroom_id,
            title=title,
            description=description,
            exam_type=exam_type,
            status=ExamStatus.READY,
            duration_minutes=duration_minutes,
            starts_at=starts_at,
            ends_at=ends_at,
            allow_retake=allow_retake,
        )
        exam.criteria = [
            ExamCriterion(
                exam_id=exam.id,
                title=criterion.title,
                description=criterion.description,
                weight=criterion.weight,
                sort_order=criterion.sort_order,
                excellent_definition=criterion.excellent_definition,
                average_definition=criterion.average_definition,
                poor_definition=criterion.poor_definition,
            )
            for criterion in criteria
        ]
        return exam

    def belongs_to_classroom(self, classroom_id: UUID) -> bool:
        return self.classroom_id == classroom_id

    def start_session(
        self,
        *,
        student_id: UUID,
        started_at: datetime,
        attempt_number: int,
        expires_at: datetime | None = None,
        provider_session_id: str | None = None,
    ) -> "ExamSession":
        return ExamSession.start(
            exam_id=self.id,
            student_id=student_id,
            started_at=started_at,
            attempt_number=attempt_number,
            expires_at=expires_at,
            provider_session_id=provider_session_id,
        )

    def record_turn(
        self,
        *,
        session: "ExamSession",
        student_id: UUID,
        role: ExamTurnRole,
        event_type: ExamTurnEventType,
        content: str,
        created_at: datetime,
        metadata: dict[str, str],
        existing_turns: Sequence["ExamTurn"],
    ) -> "ExamTurn":
        session.assert_owned_by(exam_id=self.id, student_id=student_id)
        return session.next_turn(
            role=role,
            event_type=event_type,
            content=content,
            created_at=created_at,
            metadata=metadata,
            existing_turns=existing_turns,
        )

    def complete_session(
        self,
        *,
        session: "ExamSession",
        student_id: UUID,
        occurred_at: datetime,
    ) -> None:
        session.assert_owned_by(exam_id=self.id, student_id=student_id)
        session.complete(occurred_at)

    def finalize_result(
        self,
        *,
        session: "ExamSession",
        student_id: UUID,
        results: Sequence["ExamResult"],
        overall_score: float,
        summary: str,
        submitted_at: datetime,
    ) -> "ExamResult":
        session.assert_owned_by(exam_id=self.id, student_id=student_id)
        session.assert_completed()
        result = self.find_result_for_session(
            results=results,
            session_id=session.id,
        )
        result.finalize(
            overall_score=overall_score,
            summary=summary,
            submitted_at=submitted_at,
        )
        return result

    def find_result_for_session(
        self,
        *,
        results: Sequence["ExamResult"],
        session_id: UUID,
    ) -> "ExamResult":
        for result in results:
            if result.belongs_to(session_id=session_id):
                return result
        raise AuthForbiddenException()

    def build_realtime_instructions(self) -> str:
        criteria_lines = "\n".join(
            (
                (
                    f"- {criterion.sort_order}. {criterion.title} "
                    f"({criterion.weight}%)"
                )
                + (
                    f": {criterion.description}"
                    if criterion.description
                    else ""
                )
            )
            for criterion in self.criteria
        )
        return (
            f"시험 제목: {self.title}\n"
            f"시험 설명: {self.description or '설명 없음'}\n"
            f"시험 유형: {self.exam_type.value}\n"
            f"제한 시간(분): {self.duration_minutes}\n"
            "평가 기준:\n"
            f"{criteria_lines}"
        )


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

    @classmethod
    def start(
        cls,
        *,
        exam_id: UUID,
        student_id: UUID,
        started_at: datetime,
        attempt_number: int,
        expires_at: datetime | None = None,
        provider_session_id: str | None = None,
    ) -> "ExamSession":
        return cls(
            exam_id=exam_id,
            student_id=student_id,
            status=ExamSessionStatus.IN_PROGRESS,
            started_at=started_at,
            last_activity_at=started_at,
            attempt_number=attempt_number,
            expires_at=expires_at,
            provider_session_id=provider_session_id,
        )

    def assert_owned_by(
        self,
        *,
        exam_id: UUID,
        student_id: UUID,
    ) -> None:
        if self.exam_id != exam_id or self.student_id != student_id:
            raise AuthForbiddenException()

    def record_activity(self, occurred_at: datetime) -> None:
        self.last_activity_at = occurred_at

    def next_turn(
        self,
        *,
        role: ExamTurnRole,
        event_type: ExamTurnEventType,
        content: str,
        created_at: datetime,
        metadata: dict[str, str],
        existing_turns: Sequence["ExamTurn"],
    ) -> "ExamTurn":
        self.record_activity(created_at)
        return ExamTurn.create(
            session_id=self.id,
            sequence=len(existing_turns) + 1,
            role=role,
            event_type=event_type,
            content=content,
            created_at=created_at,
            metadata=metadata,
        )

    def complete(self, occurred_at: datetime) -> None:
        self.status = ExamSessionStatus.COMPLETED
        self.ended_at = occurred_at
        self.last_activity_at = occurred_at

    def create_pending_result(self) -> "ExamResult":
        return ExamResult.pending(
            exam_id=self.exam_id,
            session_id=self.id,
            student_id=self.student_id,
        )

    def assert_completed(self) -> None:
        if self.status is not ExamSessionStatus.COMPLETED:
            raise AuthForbiddenException()


@dataclass
class ExamTurn(Entity):
    session_id: UUID
    sequence: int
    role: ExamTurnRole
    event_type: ExamTurnEventType
    content: str
    created_at: datetime
    metadata: dict[str, str] = field(default_factory=dict)

    @classmethod
    def create(
        cls,
        *,
        session_id: UUID,
        sequence: int,
        role: ExamTurnRole,
        event_type: ExamTurnEventType,
        content: str,
        created_at: datetime,
        metadata: dict[str, str],
    ) -> "ExamTurn":
        return cls(
            session_id=session_id,
            sequence=sequence,
            role=role,
            event_type=event_type,
            content=content,
            created_at=created_at,
            metadata=metadata,
        )


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

    @classmethod
    def pending(
        cls,
        *,
        exam_id: UUID,
        session_id: UUID,
        student_id: UUID,
    ) -> "ExamResult":
        return cls(
            exam_id=exam_id,
            session_id=session_id,
            student_id=student_id,
            status=ExamResultStatus.PENDING,
        )

    def belongs_to(
        self,
        *,
        session_id: UUID,
    ) -> bool:
        return self.session_id == session_id

    def finalize(
        self,
        *,
        overall_score: float,
        summary: str,
        submitted_at: datetime,
    ) -> None:
        self.status = ExamResultStatus.COMPLETED
        self.submitted_at = submitted_at
        self.overall_score = overall_score
        self.summary = summary


@dataclass(frozen=True)
class RealtimeClientSecret:
    value: str
    expires_at: datetime | None = None
    provider_session_id: str | None = None


@dataclass(frozen=True)
class StartedExamSession:
    session: ExamSession
    client_secret: str
