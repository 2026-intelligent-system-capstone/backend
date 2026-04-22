from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from uuid import UUID

from app.exam.domain.exception import (
    ExamInvalidMaxAttemptsDomainException,
    ExamInvalidWeekDomainException,
    ExamQuestionNotFoundDomainException,
    ExamResultNotFoundDomainException,
    ExamSessionAlreadyInProgressDomainException,
    ExamSessionMaxAttemptsExceededDomainException,
    ExamSessionNotCompletedDomainException,
    ExamSessionOwnershipForbiddenDomainException,
)
from core.common.entity import AggregateRoot, Entity


class ExamType(StrEnum):
    WEEKLY = "weekly"
    MIDTERM = "midterm"
    FINAL = "final"
    MOCK = "mock"
    PROJECT = "project"


class ExamStatus(StrEnum):
    READY = "ready"
    IN_PROGRESS = "in_progress"
    CLOSED = "closed"


class ExamDifficulty(StrEnum):
    EASY = "easy"
    MEDIUM = "medium"
    HARD = "hard"


class ExamGenerationStatus(StrEnum):
    IDLE = "idle"
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class BloomLevel(StrEnum):
    NONE = "none"
    REMEMBER = "remember"
    UNDERSTAND = "understand"
    APPLY = "apply"
    ANALYZE = "analyze"
    EVALUATE = "evaluate"
    CREATE = "create"


class ExamQuestionType(StrEnum):
    NONE = "none"
    MULTIPLE_CHOICE = "multiple_choice"
    SUBJECTIVE = "subjective"
    ORAL = "oral"


class ExamQuestionTypeStrategy(StrEnum):
    BALANCED = "balanced"
    MULTIPLE_CHOICE_FOCUS = "multiple_choice_focus"
    SUBJECTIVE_FOCUS = "subjective_focus"
    ORAL_FOCUS = "oral_focus"

    def ordered_question_types(self) -> tuple[ExamQuestionType, ...]:
        if self is ExamQuestionTypeStrategy.ORAL_FOCUS:
            return (
                ExamQuestionType.ORAL,
                ExamQuestionType.SUBJECTIVE,
                ExamQuestionType.MULTIPLE_CHOICE,
            )
        if self is ExamQuestionTypeStrategy.SUBJECTIVE_FOCUS:
            return (
                ExamQuestionType.SUBJECTIVE,
                ExamQuestionType.ORAL,
                ExamQuestionType.MULTIPLE_CHOICE,
            )
        if self is ExamQuestionTypeStrategy.MULTIPLE_CHOICE_FOCUS:
            return (
                ExamQuestionType.MULTIPLE_CHOICE,
                ExamQuestionType.SUBJECTIVE,
                ExamQuestionType.ORAL,
            )
        return (
            ExamQuestionType.MULTIPLE_CHOICE,
            ExamQuestionType.SUBJECTIVE,
            ExamQuestionType.ORAL,
        )

    def weighted_cycle(self) -> tuple[ExamQuestionType, ...]:
        if self is ExamQuestionTypeStrategy.ORAL_FOCUS:
            return (
                ExamQuestionType.ORAL,
                ExamQuestionType.ORAL,
                ExamQuestionType.ORAL,
                ExamQuestionType.SUBJECTIVE,
                ExamQuestionType.MULTIPLE_CHOICE,
            )
        if self is ExamQuestionTypeStrategy.SUBJECTIVE_FOCUS:
            return (
                ExamQuestionType.SUBJECTIVE,
                ExamQuestionType.SUBJECTIVE,
                ExamQuestionType.SUBJECTIVE,
                ExamQuestionType.ORAL,
                ExamQuestionType.MULTIPLE_CHOICE,
            )
        if self is ExamQuestionTypeStrategy.MULTIPLE_CHOICE_FOCUS:
            return (
                ExamQuestionType.MULTIPLE_CHOICE,
                ExamQuestionType.MULTIPLE_CHOICE,
                ExamQuestionType.MULTIPLE_CHOICE,
                ExamQuestionType.SUBJECTIVE,
                ExamQuestionType.ORAL,
            )
        return self.ordered_question_types()


class ExamQuestionStatus(StrEnum):
    GENERATED = "generated"
    REVIEWED = "reviewed"
    DELETED = "deleted"


EXAM_GENERATION_ERROR_MAX_LENGTH = 1000


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
class ExamQuestion(Entity):
    exam_id: UUID
    question_number: int
    max_score: float
    question_type: ExamQuestionType = ExamQuestionType.NONE
    bloom_level: BloomLevel = BloomLevel.NONE
    difficulty: ExamDifficulty = ExamDifficulty.MEDIUM
    question_text: str = ""
    intent_text: str = ""
    rubric_text: str = ""
    answer_options: list[str] = field(default_factory=list)
    correct_answer_text: str | None = None
    source_material_ids: list[UUID] = field(default_factory=list)
    status: ExamQuestionStatus = ExamQuestionStatus.GENERATED

    def __post_init__(self) -> None:
        self._validate_max_score()
        self._normalize_answer_fields()

    def belongs_to_exam(self, exam_id: UUID) -> bool:
        return self.exam_id == exam_id

    def revise(
        self,
        *,
        question_number: int | None = None,
        max_score: float | None = None,
        question_type: ExamQuestionType | None = None,
        bloom_level: BloomLevel | None = None,
        difficulty: ExamDifficulty | None = None,
        question_text: str | None = None,
        intent_text: str | None = None,
        rubric_text: str | None = None,
        answer_options: Sequence[str] | None = None,
        correct_answer_text: str | None = None,
        source_material_ids: Sequence[UUID] | None = None,
    ) -> None:
        previous_question_type = self.question_type
        next_question_type = question_type or self.question_type

        if question_number is not None:
            self.question_number = question_number
        if max_score is not None:
            self.max_score = max_score
        if question_type is not None:
            self.question_type = question_type
        if bloom_level is not None:
            self.bloom_level = bloom_level
        if difficulty is not None:
            self.difficulty = difficulty
        if question_text is not None:
            self.question_text = question_text
        if intent_text is not None:
            self.intent_text = intent_text
        if rubric_text is not None:
            self.rubric_text = rubric_text
        if answer_options is not None:
            self.answer_options = list(answer_options)
        if (
            correct_answer_text is not None
            or next_question_type is ExamQuestionType.ORAL
        ):
            self.correct_answer_text = correct_answer_text
        elif (
            question_type is not None
            and previous_question_type is ExamQuestionType.MULTIPLE_CHOICE
            and next_question_type is not ExamQuestionType.MULTIPLE_CHOICE
        ):
            self.correct_answer_text = None
        if source_material_ids is not None:
            self.source_material_ids = list(source_material_ids)
        self._validate_max_score()
        self._normalize_answer_fields()
        if self.status is not ExamQuestionStatus.DELETED:
            self.status = ExamQuestionStatus.REVIEWED

    def delete(self) -> None:
        self.status = ExamQuestionStatus.DELETED

    def _validate_max_score(self) -> None:
        if self.max_score <= 0:
            raise ValueError("max_score must be greater than 0")

    def _normalize_answer_fields(self) -> None:
        normalized_options = [
            str(option).strip()
            for option in self.answer_options
            if str(option).strip()
        ]
        self.answer_options = normalized_options
        self.correct_answer_text = (
            self.correct_answer_text.strip()
            if isinstance(self.correct_answer_text, str)
            and self.correct_answer_text.strip()
            else None
        )
        if self.question_type is ExamQuestionType.MULTIPLE_CHOICE:
            if self.answer_options and (
                self.correct_answer_text is None
                or self.correct_answer_text not in self.answer_options
            ):
                raise ValueError(
                    "multiple_choice correct_answer_text must match one of "
                    "answer_options"
                )
            return
        self.answer_options = []
        if self.question_type is ExamQuestionType.ORAL:
            self.correct_answer_text = None


@dataclass
class Exam(AggregateRoot):
    classroom_id: UUID
    title: str
    exam_type: ExamType
    duration_minutes: int
    starts_at: datetime
    ends_at: datetime
    max_attempts: int
    week: int
    description: str | None = None
    status: ExamStatus = ExamStatus.READY
    generation_status: ExamGenerationStatus = ExamGenerationStatus.IDLE
    generation_error: str | None = None
    generation_job_id: UUID | None = None
    generation_requested_at: datetime | None = None
    generation_completed_at: datetime | None = None
    criteria: list[ExamCriterion] = field(default_factory=list)
    questions: list[ExamQuestion] = field(default_factory=list)

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
        max_attempts: int,
        week: int,
        criteria: Sequence[ExamCriterion],
    ) -> Exam:
        if week < 1:
            raise ExamInvalidWeekDomainException(
                message="week must be greater than or equal to 1"
            )
        if max_attempts < 1:
            raise ExamInvalidMaxAttemptsDomainException(
                message="max_attempts must be greater than or equal to 1"
            )
        exam = cls(
            classroom_id=classroom_id,
            title=title,
            description=description,
            exam_type=exam_type,
            status=ExamStatus.READY,
            duration_minutes=duration_minutes,
            starts_at=starts_at,
            ends_at=ends_at,
            max_attempts=max_attempts,
            week=week,
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

    def mark_generation_queued(
        self,
        *,
        job_id: UUID,
        requested_at: datetime,
    ) -> None:
        self.generation_status = ExamGenerationStatus.QUEUED
        self.generation_error = None
        self.generation_job_id = job_id
        self.generation_requested_at = requested_at
        self.generation_completed_at = None

    def mark_generation_running(self, *, started_at: datetime) -> None:
        self.generation_status = ExamGenerationStatus.RUNNING
        self.generation_error = None
        self.generation_requested_at = (
            self.generation_requested_at or started_at
        )
        self.generation_completed_at = None

    def mark_generation_completed(
        self,
        *,
        completed_at: datetime,
    ) -> None:
        self.generation_status = ExamGenerationStatus.COMPLETED
        self.generation_error = None
        self.generation_completed_at = completed_at

    def mark_generation_failed(
        self,
        *,
        error_message: str,
        completed_at: datetime,
    ) -> None:
        self.generation_status = ExamGenerationStatus.FAILED
        self.generation_error = error_message[:EXAM_GENERATION_ERROR_MAX_LENGTH]
        self.generation_completed_at = completed_at

    def add_question(
        self,
        *,
        question_number: int,
        max_score: float,
        question_type: ExamQuestionType = ExamQuestionType.NONE,
        bloom_level: BloomLevel,
        difficulty: ExamDifficulty,
        question_text: str,
        intent_text: str,
        rubric_text: str,
        answer_options: Sequence[str] | None = None,
        correct_answer_text: str | None = None,
        source_material_ids: Sequence[UUID],
    ) -> ExamQuestion:
        question = ExamQuestion(
            exam_id=self.id,
            question_number=question_number,
            max_score=max_score,
            question_type=question_type,
            bloom_level=bloom_level,
            difficulty=difficulty,
            question_text=question_text,
            intent_text=intent_text,
            rubric_text=rubric_text,
            answer_options=list(answer_options or []),
            correct_answer_text=correct_answer_text,
            source_material_ids=list(source_material_ids),
            status=ExamQuestionStatus.GENERATED,
        )
        self.questions.append(question)
        return question

    def find_question(self, question_id: UUID) -> ExamQuestion:
        for question in self.questions:
            if question.id == question_id and question.belongs_to_exam(self.id):
                return question
        raise ExamQuestionNotFoundDomainException(
            message="exam question not found"
        )

    def update_question(
        self,
        *,
        question_id: UUID,
        question_number: int | None = None,
        max_score: float | None = None,
        question_type: ExamQuestionType | None = None,
        bloom_level: BloomLevel | None = None,
        difficulty: ExamDifficulty | None = None,
        question_text: str | None = None,
        intent_text: str | None = None,
        rubric_text: str | None = None,
        answer_options: Sequence[str] | None = None,
        correct_answer_text: str | None = None,
        source_material_ids: Sequence[UUID] | None = None,
    ) -> ExamQuestion:
        question = self.find_question(question_id)
        question.revise(
            question_number=question_number,
            max_score=max_score,
            question_type=question_type,
            bloom_level=bloom_level,
            difficulty=difficulty,
            question_text=question_text,
            intent_text=intent_text,
            rubric_text=rubric_text,
            answer_options=answer_options,
            correct_answer_text=correct_answer_text,
            source_material_ids=source_material_ids,
        )
        return question

    def delete_question(self, question_id: UUID) -> ExamQuestion:
        question = self.find_question(question_id)
        question.delete()
        return question

    def resolve_next_attempt_number(
        self,
        *,
        sessions: Sequence[ExamSession],
    ) -> int:
        if any(
            session.status is ExamSessionStatus.IN_PROGRESS
            for session in sessions
        ):
            raise ExamSessionAlreadyInProgressDomainException()
        next_attempt_number = (
            max(
                (session.attempt_number for session in sessions),
                default=0,
            )
            + 1
        )
        if next_attempt_number > self.max_attempts:
            raise ExamSessionMaxAttemptsExceededDomainException()
        return next_attempt_number

    def start_session(
        self,
        *,
        student_id: UUID,
        started_at: datetime,
        attempt_number: int,
        expires_at: datetime | None = None,
        provider_session_id: str | None = None,
    ) -> ExamSession:
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
        session: ExamSession,
        student_id: UUID,
        role: ExamTurnRole,
        event_type: ExamTurnEventType,
        content: str,
        created_at: datetime,
        metadata: dict[str, str],
        existing_turns: Sequence[ExamTurn],
    ) -> ExamTurn:
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
        session: ExamSession,
        student_id: UUID,
        occurred_at: datetime,
    ) -> None:
        session.assert_owned_by(exam_id=self.id, student_id=student_id)
        session.complete(occurred_at)

    def finalize_result(
        self,
        *,
        session: ExamSession,
        student_id: UUID,
        results: Sequence[ExamResult],
    ) -> ExamResult:
        session.assert_owned_by(exam_id=self.id, student_id=student_id)
        session.assert_completed()
        return self.find_result_for_session(
            results=results,
            session_id=session.id,
        )

    def find_result_for_session(
        self,
        *,
        results: Sequence[ExamResult],
        session_id: UUID,
    ) -> ExamResult:
        for result in results:
            if result.belongs_to(session_id=session_id):
                return result
        raise ExamResultNotFoundDomainException()

    def build_realtime_instructions(self) -> str:
        criteria_lines = "\n".join(
            (
                f"- {criterion.sort_order}. {criterion.title} "
                f"({criterion.weight}%)"
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
    ) -> ExamSession:
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
            raise ExamSessionOwnershipForbiddenDomainException()

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
        existing_turns: Sequence[ExamTurn],
    ) -> ExamTurn:
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

    def create_pending_result(self) -> ExamResult:
        return ExamResult.pending(
            exam_id=self.exam_id,
            session_id=self.id,
            student_id=self.student_id,
        )

    def assert_completed(self) -> None:
        if self.status is not ExamSessionStatus.COMPLETED:
            raise ExamSessionNotCompletedDomainException()


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
    ) -> ExamTurn:
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
    ) -> ExamResult:
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
        strengths: Sequence[str] | None = None,
        weaknesses: Sequence[str] | None = None,
        improvement_suggestions: Sequence[str] | None = None,
        criteria_results: Sequence[ExamResultCriterion] | None = None,
    ) -> None:
        self.status = ExamResultStatus.COMPLETED
        self.submitted_at = submitted_at
        self.overall_score = overall_score
        self.summary = summary
        self.strengths = list(strengths or [])
        self.weaknesses = list(weaknesses or [])
        self.improvement_suggestions = list(improvement_suggestions or [])
        self.criteria_results = list(criteria_results or [])

    def finalize_from_evaluation(
        self,
        *,
        summary: str,
        strengths: Sequence[str],
        weaknesses: Sequence[str],
        improvement_suggestions: Sequence[str],
        criteria_results: Sequence[ExamResultCriterion],
        criteria: Sequence[ExamCriterion],
        submitted_at: datetime | None = None,
    ) -> None:
        criteria_by_id = {criterion.id: criterion for criterion in criteria}
        expected_criterion_ids = set(criteria_by_id)
        actual_criterion_ids = {
            criterion_result.criterion_id
            for criterion_result in criteria_results
        }
        if actual_criterion_ids != expected_criterion_ids:
            raise ValueError("criterion 결과가 시험 기준과 일치하지 않습니다.")

        weighted_score_sum = 0.0
        total_weight = 0
        for criterion_result in criteria_results:
            if criterion_result.score is None:
                continue
            criterion = criteria_by_id[criterion_result.criterion_id]
            weighted_score_sum += criterion_result.score * criterion.weight
            total_weight += criterion.weight
        overall_score = (
            weighted_score_sum / total_weight if total_weight > 0 else 0.0
        )
        self.finalize(
            overall_score=overall_score,
            summary=summary,
            submitted_at=submitted_at or datetime.now(UTC),
            strengths=strengths,
            weaknesses=weaknesses,
            improvement_suggestions=improvement_suggestions,
            criteria_results=criteria_results,
        )


@dataclass(frozen=True)
class RealtimeClientSecret:
    value: str
    expires_at: datetime | None = None
    provider_session_id: str | None = None


@dataclass(frozen=True)
class StartedExamSession:
    session: ExamSession
    client_secret: str


@dataclass(frozen=True)
class StudentExam:
    exam: Exam
    is_completed: bool
    can_enter: bool
    latest_result: ExamResult | None = None
