from collections.abc import Sequence
from datetime import UTC, datetime, timedelta
from uuid import UUID

import pytest
from sqlalchemy.exc import IntegrityError

from app.async_job.domain.entity import (
    AsyncJob,
    AsyncJobTargetType,
    AsyncJobType,
)
from app.auth.application.exception import AuthForbiddenException
from app.auth.domain.entity import CurrentUser
from app.classroom.domain.entity import Classroom
from app.classroom.domain.usecase import ClassroomUseCase
from app.exam.application.exception import (
    ExamSessionAlreadyInProgressException,
    ExamSessionMaxAttemptsExceededException,
    ExamSessionUnavailableException,
)
from app.exam.application.service import ExamService
from app.exam.domain.command import (
    CompleteExamSessionCommand,
    FinalizeExamResultCommand,
    RecordExamTurnCommand,
)
from app.exam.domain.entity import (
    Exam,
    ExamCriterion,
    ExamResult,
    ExamResultCriterion,
    ExamResultStatus,
    ExamSession,
    ExamSessionStatus,
    ExamStatus,
    ExamTurn,
    ExamTurnEventType,
    ExamTurnRole,
    ExamType,
    RealtimeClientSecret,
)
from app.exam.domain.exception import (
    ExamSessionNotCompletedDomainException,
    ExamSessionOwnershipForbiddenDomainException,
)
from app.exam.domain.repository import (
    ExamRepository,
    ExamResultRepository,
    ExamSessionRepository,
    ExamTurnRepository,
)
from app.exam.domain.service import RealtimeSessionPort
from app.user.domain.entity import UserRole

ORG_ID = UUID("11111111-1111-1111-1111-111111111111")
CLASSROOM_ID = UUID("22222222-2222-2222-2222-222222222222")
EXAM_ID = UUID("33333333-3333-3333-3333-333333333333")
PROFESSOR_ID = UUID("44444444-4444-4444-4444-444444444444")
STUDENT_ID = UUID("55555555-5555-5555-5555-555555555555")
NOW = datetime.now(UTC)
STARTS_AT = NOW - timedelta(minutes=5)
ENDS_AT = NOW + timedelta(hours=1)
SECRET_EXPIRES_AT = NOW + timedelta(minutes=55)
WEEK = 1


class InMemoryExamRepository(ExamRepository):
    def __init__(self, exams: list[Exam] | None = None):
        self.exams = {exam.id: exam for exam in exams or []}

    async def save(self, entity: Exam) -> None:
        self.exams[entity.id] = entity

    async def get_by_id(self, entity_id: UUID) -> Exam | None:
        return self.exams.get(entity_id)

    async def list(self) -> Sequence[Exam]:
        return list(self.exams.values())

    async def list_by_classroom(self, classroom_id: UUID) -> Sequence[Exam]:
        return [
            exam
            for exam in self.exams.values()
            if exam.classroom_id == classroom_id
        ]


class InMemoryExamSessionRepository(ExamSessionRepository):
    def __init__(self):
        self.sessions: dict[UUID, ExamSession] = {}
        self.raise_on_save: IntegrityError | None = None

    async def save(self, entity: ExamSession) -> None:
        if self.raise_on_save is not None:
            raise self.raise_on_save
        self.sessions[entity.id] = entity

    async def get_by_id(self, entity_id: UUID) -> ExamSession | None:
        return self.sessions.get(entity_id)

    async def list(self) -> Sequence[ExamSession]:
        return list(self.sessions.values())

    async def list_by_exam_and_student(
        self,
        *,
        exam_id: UUID,
        student_id: UUID,
    ) -> Sequence[ExamSession]:
        return [
            session
            for session in self.sessions.values()
            if session.exam_id == exam_id and session.student_id == student_id
        ]

    async def list_by_exam_and_student_for_update(
        self,
        *,
        exam_id: UUID,
        student_id: UUID,
    ) -> Sequence[ExamSession]:
        return await self.list_by_exam_and_student(
            exam_id=exam_id,
            student_id=student_id,
        )


class InMemoryExamResultRepository(ExamResultRepository):
    def __init__(self):
        self.results: dict[UUID, ExamResult] = {}

    async def save(self, entity: ExamResult) -> None:
        self.results[entity.id] = entity

    async def get_by_id(self, entity_id: UUID) -> ExamResult | None:
        return self.results.get(entity_id)

    async def list(self) -> Sequence[ExamResult]:
        return list(self.results.values())

    async def list_by_exam_and_student(
        self,
        *,
        exam_id: UUID,
        student_id: UUID,
    ) -> Sequence[ExamResult]:
        return [
            result
            for result in self.results.values()
            if result.exam_id == exam_id and result.student_id == student_id
        ]

    async def list_by_exam_and_student_for_update(
        self,
        *,
        exam_id: UUID,
        student_id: UUID,
    ) -> Sequence[ExamResult]:
        return await self.list_by_exam_and_student(
            exam_id=exam_id,
            student_id=student_id,
        )


class InMemoryExamTurnRepository(ExamTurnRepository):
    def __init__(self):
        self.turns: dict[UUID, ExamTurn] = {}

    async def save(self, entity: ExamTurn) -> None:
        self.turns[entity.id] = entity

    async def get_by_id(self, entity_id: UUID) -> ExamTurn | None:
        return self.turns.get(entity_id)

    async def list(self) -> Sequence[ExamTurn]:
        return list(self.turns.values())

    async def list_by_session(self, *, session_id: UUID) -> Sequence[ExamTurn]:
        return [
            turn
            for turn in sorted(
                self.turns.values(), key=lambda item: item.sequence
            )
            if turn.session_id == session_id
        ]


class FakeRealtimeSessionPort(RealtimeSessionPort):
    def __init__(self):
        self.calls: list[dict[str, str]] = []

    async def create_client_secret(
        self,
        *,
        instructions: str,
    ) -> RealtimeClientSecret:
        self.calls.append({"instructions": instructions})
        return RealtimeClientSecret(
            value="ek_test_secret",
            expires_at=SECRET_EXPIRES_AT,
            provider_session_id="sess_test_123",
        )


class FailIfSecretCreatedRealtimeSessionPort(RealtimeSessionPort):
    async def create_client_secret(
        self,
        *,
        _instructions: str,
    ) -> RealtimeClientSecret:
        raise AssertionError(
            "create_client_secret must not be called before session "
            "persistence succeeds"
        )


class CompletedResultAppearsAfterLockSessionRepository(
    InMemoryExamSessionRepository
):
    def __init__(self, *, result_repository: InMemoryExamResultRepository):
        super().__init__()
        self.result_repository = result_repository
        self.completed_result_injected = False

    async def list_by_exam_and_student_for_update(
        self,
        *,
        exam_id: UUID,
        student_id: UUID,
    ) -> Sequence[ExamSession]:
        if not self.completed_result_injected:
            completed_result = ExamResult(
                exam_id=exam_id,
                session_id=UUID("77777777-7777-7777-7777-777777777777"),
                student_id=student_id,
                status=ExamResultStatus.COMPLETED,
                submitted_at=ENDS_AT,
            )
            await self.result_repository.save(completed_result)
            self.completed_result_injected = True
        return await super().list_by_exam_and_student_for_update(
            exam_id=exam_id,
            student_id=student_id,
        )


class CompletedResultAppearsDuringResultLockRepository(
    InMemoryExamResultRepository
):
    def __init__(self):
        super().__init__()
        self.completed_result_injected = False

    async def list_by_exam_and_student_for_update(
        self,
        *,
        exam_id: UUID,
        student_id: UUID,
    ) -> Sequence[ExamResult]:
        if not self.completed_result_injected:
            completed_result = ExamResult(
                exam_id=exam_id,
                session_id=UUID("88888888-8888-8888-8888-888888888888"),
                student_id=student_id,
                status=ExamResultStatus.COMPLETED,
                submitted_at=ENDS_AT,
            )
            await self.save(completed_result)
            self.completed_result_injected = True
        return await super().list_by_exam_and_student_for_update(
            exam_id=exam_id,
            student_id=student_id,
        )


class FailOnSecondSessionSaveRepository(InMemoryExamSessionRepository):
    def __init__(self):
        super().__init__()
        self.save_calls = 0

    async def save(self, entity: ExamSession) -> None:
        self.save_calls += 1
        if self.save_calls == 2:
            raise AssertionError("session must not be persisted twice")
        await super().save(entity)


class FakeAsyncJobService:
    def __init__(self):
        self.jobs: list[AsyncJob] = []
        self.enqueue_calls: list[dict[str, object]] = []

    async def enqueue(
        self,
        *,
        job_type: AsyncJobType,
        target_type: AsyncJobTargetType,
        target_id: UUID,
        requested_by: UUID,
        payload: dict[str, object],
        dedupe_key: str | None = None,
    ) -> AsyncJob:
        self.enqueue_calls.append({
            "job_type": job_type,
            "target_type": target_type,
            "target_id": target_id,
            "requested_by": requested_by,
            "payload": payload,
            "dedupe_key": dedupe_key,
        })
        job = AsyncJob.enqueue(
            job_type=job_type,
            target_type=target_type,
            target_id=target_id,
            requested_by=requested_by,
            payload=payload,
            dedupe_key=dedupe_key,
        )
        self.jobs.append(job)
        return job


class FakeClassroomUseCase(ClassroomUseCase):
    def __init__(self, classroom: Classroom):
        self.classroom = classroom

    async def create_classroom(self, *, current_user, command) -> Classroom:
        raise NotImplementedError

    async def get_classroom(
        self,
        *,
        classroom_id: UUID,
        current_user: CurrentUser,
    ) -> Classroom:
        _ = current_user
        if classroom_id != self.classroom.id:
            raise AuthForbiddenException()
        return self.classroom

    async def get_manageable_classroom(
        self,
        *,
        classroom_id: UUID,
        current_user: CurrentUser,
    ) -> Classroom:
        return await self.get_classroom(
            classroom_id=classroom_id,
            current_user=current_user,
        )

    async def list_classrooms(
        self, *, current_user: CurrentUser
    ) -> list[Classroom]:
        raise NotImplementedError

    async def update_classroom(
        self, *, classroom_id, current_user, command
    ) -> Classroom:
        raise NotImplementedError

    async def delete_classroom(
        self, *, classroom_id, current_user
    ) -> Classroom:
        raise NotImplementedError

    async def remove_classroom_student(
        self, *, classroom_id, current_user, command
    ) -> Classroom:
        raise NotImplementedError

    async def invite_classroom_students(
        self, *, classroom_id, current_user, command
    ) -> Classroom:
        raise NotImplementedError

    async def create_classroom_material(
        self,
        *,
        classroom_id,
        current_user,
        command,
        file_upload,
    ):
        raise NotImplementedError

    async def list_classroom_materials(
        self,
        *,
        classroom_id,
        current_user,
    ):
        raise NotImplementedError

    async def get_classroom_material(
        self,
        *,
        classroom_id,
        material_id,
        current_user,
    ):
        raise NotImplementedError

    async def get_classroom_material_download(
        self,
        *,
        classroom_id,
        material_id,
        current_user,
    ):
        raise NotImplementedError

    async def update_classroom_material(
        self,
        *,
        classroom_id,
        material_id,
        current_user,
        command,
        file_upload=None,
    ):
        raise NotImplementedError

    async def reingest_classroom_material(
        self,
        *,
        classroom_id,
        material_id,
        current_user,
    ):
        raise NotImplementedError

    async def delete_classroom_material(
        self,
        *,
        classroom_id,
        material_id,
        current_user,
    ):
        raise NotImplementedError


def make_classroom() -> Classroom:
    classroom = Classroom(
        organization_id=ORG_ID,
        name="AI 기초",
        professor_ids=[PROFESSOR_ID],
        student_ids=[STUDENT_ID],
    )
    classroom.id = CLASSROOM_ID
    return classroom


def make_exam(*, max_attempts: int = 1) -> Exam:
    exam = Exam(
        classroom_id=CLASSROOM_ID,
        title="중간 평가",
        description="1주차 범위 평가",
        exam_type=ExamType.MIDTERM,
        status=ExamStatus.READY,
        duration_minutes=60,
        starts_at=STARTS_AT,
        ends_at=ENDS_AT,
        max_attempts=max_attempts,
        week=WEEK,
        criteria=[
            ExamCriterion(
                exam_id=EXAM_ID,
                title="개념 이해",
                description="핵심 개념을 설명하는지 평가",
                weight=70,
                sort_order=1,
                excellent_definition="개념 관계를 정확히 설명한다.",
                average_definition="개념 설명은 가능하나 연결이 약하다.",
                poor_definition="개념 이해가 부족하다.",
            ),
            ExamCriterion(
                exam_id=EXAM_ID,
                title="문제 해결 과정",
                description="풀이 근거와 절차를 평가",
                weight=30,
                sort_order=2,
                excellent_definition="근거와 절차가 명확하다.",
                average_definition="절차는 맞지만 근거가 약하다.",
                poor_definition="풀이 과정이 불명확하다.",
            ),
        ],
    )
    exam.id = EXAM_ID
    return exam


def make_current_user(*, role: UserRole, user_id: UUID) -> CurrentUser:
    return CurrentUser(
        id=user_id,
        organization_id=ORG_ID,
        login_id="user01",
        role=role,
    )


def test_exam_session_entity_methods_enforce_rules():
    session = ExamSession.start(
        exam_id=EXAM_ID,
        student_id=STUDENT_ID,
        started_at=STARTS_AT,
        attempt_number=1,
        expires_at=SECRET_EXPIRES_AT,
        provider_session_id="sess_test_123",
    )

    assert session.status is ExamSessionStatus.IN_PROGRESS
    assert session.last_activity_at == STARTS_AT

    session.record_activity(ENDS_AT)
    assert session.last_activity_at == ENDS_AT

    with pytest.raises(ExamSessionOwnershipForbiddenDomainException):
        session.assert_owned_by(
            exam_id=EXAM_ID,
            student_id=PROFESSOR_ID,
        )

    pending_result = session.create_pending_result()
    assert pending_result.session_id == session.id
    assert pending_result.student_id == STUDENT_ID
    assert pending_result.status is ExamResultStatus.PENDING

    session.complete(ENDS_AT)
    session.assert_completed()
    assert session.ended_at == ENDS_AT


def test_exam_result_entity_methods_finalize_result():
    result = ExamResult.pending(
        exam_id=EXAM_ID,
        session_id=UUID("66666666-6666-6666-6666-666666666666"),
        student_id=STUDENT_ID,
    )

    assert result.status is ExamResultStatus.PENDING
    assert result.belongs_to(session_id=result.session_id) is True

    result.finalize(
        overall_score=95,
        summary="전반적으로 우수합니다.",
        submitted_at=ENDS_AT,
    )

    assert result.status is ExamResultStatus.COMPLETED
    assert result.overall_score == 95
    assert result.summary == "전반적으로 우수합니다."
    assert result.submitted_at == ENDS_AT


def test_exam_result_finalize_from_evaluation_uses_weighted_score():
    result = ExamResult.pending(
        exam_id=EXAM_ID,
        session_id=UUID("66666666-6666-6666-6666-666666666666"),
        student_id=STUDENT_ID,
    )
    criteria = [
        ExamCriterion(
            exam_id=EXAM_ID,
            title="개념 이해",
            description=None,
            weight=70,
            sort_order=1,
        ),
        ExamCriterion(
            exam_id=EXAM_ID,
            title="문제 해결",
            description=None,
            weight=30,
            sort_order=2,
        ),
    ]
    criteria[0].id = UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
    criteria[1].id = UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")

    result.finalize_from_evaluation(
        summary="가중치 기준 평가 완료",
        strengths=["개념 이해가 우수합니다."],
        weaknesses=["문제 해결 근거가 부족합니다."],
        improvement_suggestions=["적용 예시를 더 연습하세요."],
        criteria_results=[
            ExamResultCriterion(
                criterion_id=criteria[0].id,
                score=100,
                feedback="핵심 개념을 정확히 설명했습니다.",
            ),
            ExamResultCriterion(
                criterion_id=criteria[1].id,
                score=50,
                feedback="적용 근거 설명이 부족합니다.",
            ),
        ],
        criteria=criteria,
        submitted_at=ENDS_AT,
    )

    assert result.status is ExamResultStatus.COMPLETED
    assert result.overall_score == 85
    assert result.summary == "가중치 기준 평가 완료"


def test_exam_result_finalize_from_evaluation_rejects_missing_criteria():
    result = ExamResult.pending(
        exam_id=EXAM_ID,
        session_id=UUID("66666666-6666-6666-6666-666666666666"),
        student_id=STUDENT_ID,
    )
    criteria = [
        ExamCriterion(
            exam_id=EXAM_ID,
            title="개념 이해",
            description=None,
            weight=50,
            sort_order=1,
        ),
        ExamCriterion(
            exam_id=EXAM_ID,
            title="문제 해결",
            description=None,
            weight=50,
            sort_order=2,
        ),
    ]
    criteria[0].id = UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
    criteria[1].id = UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")

    with pytest.raises(
        ValueError, match="criterion 결과가 시험 기준과 일치하지 않습니다"
    ):
        result.finalize_from_evaluation(
            summary="부분 평가",
            strengths=[],
            weaknesses=[],
            improvement_suggestions=[],
            criteria_results=[
                ExamResultCriterion(
                    criterion_id=criteria[0].id,
                    score=90,
                    feedback="개념 설명은 좋습니다.",
                )
            ],
            criteria=criteria,
            submitted_at=ENDS_AT,
        )


def test_exam_turn_entity_create_preserves_payload():
    turn = ExamTurn.create(
        session_id=UUID("66666666-6666-6666-6666-666666666666"),
        sequence=3,
        role=ExamTurnRole.ASSISTANT,
        event_type=ExamTurnEventType.FOLLOW_UP,
        content="추가 질문입니다.",
        created_at=ENDS_AT,
        metadata={"message_id": "msg-follow-up-1"},
    )

    assert turn.sequence == 3
    assert turn.event_type is ExamTurnEventType.FOLLOW_UP
    assert turn.metadata == {"message_id": "msg-follow-up-1"}


def test_exam_aggregate_session_and_result_rules():
    exam = make_exam()
    session = exam.start_session(
        student_id=STUDENT_ID,
        started_at=STARTS_AT,
        attempt_number=1,
        expires_at=SECRET_EXPIRES_AT,
        provider_session_id="sess_test_123",
    )
    turn = exam.record_turn(
        session=session,
        student_id=STUDENT_ID,
        role=ExamTurnRole.STUDENT,
        event_type=ExamTurnEventType.ANSWER,
        content="답변입니다.",
        created_at=ENDS_AT,
        metadata={"message_id": "msg-answer-1"},
        existing_turns=[],
    )
    result = session.create_pending_result()

    assert session.exam_id == exam.id
    assert turn.sequence == 1
    assert turn.session_id == session.id
    assert session.last_activity_at == ENDS_AT
    assert (
        exam.find_result_for_session(
            results=[result],
            session_id=session.id,
        )
        is result
    )


def test_exam_aggregate_validates_ownership_and_finalize_rules():
    exam = make_exam()
    session = exam.start_session(
        student_id=STUDENT_ID,
        started_at=STARTS_AT,
        attempt_number=1,
    )
    result = session.create_pending_result()

    with pytest.raises(ExamSessionOwnershipForbiddenDomainException):
        exam.record_turn(
            session=session,
            student_id=PROFESSOR_ID,
            role=ExamTurnRole.STUDENT,
            event_type=ExamTurnEventType.ANSWER,
            content="답변",
            created_at=STARTS_AT,
            metadata={},
            existing_turns=[],
        )

    with pytest.raises(ExamSessionNotCompletedDomainException):
        exam.finalize_result(
            session=session,
            student_id=STUDENT_ID,
            results=[result],
        )

    exam.complete_session(
        session=session,
        student_id=STUDENT_ID,
        occurred_at=ENDS_AT,
    )
    finalized = exam.finalize_result(
        session=session,
        student_id=STUDENT_ID,
        results=[result],
    )

    assert finalized is result
    assert finalized.status is ExamResultStatus.PENDING
    assert finalized.overall_score is None


@pytest.mark.asyncio
async def test_start_exam_session_returns_secret_and_session():
    exam_repository = InMemoryExamRepository([make_exam()])
    session_repository = InMemoryExamSessionRepository()
    result_repository = InMemoryExamResultRepository()
    realtime_port = FakeRealtimeSessionPort()
    service = ExamService(
        repository=exam_repository,
        classroom_usecase=FakeClassroomUseCase(make_classroom()),
        session_repository=session_repository,
        result_repository=result_repository,
        turn_repository=InMemoryExamTurnRepository(),
        realtime_session_port=realtime_port,
    )

    result = await service.start_exam_session(
        exam_id=EXAM_ID,
        current_user=make_current_user(
            role=UserRole.STUDENT,
            user_id=STUDENT_ID,
        ),
    )

    assert result.client_secret == "ek_test_secret"
    assert result.session.exam_id == EXAM_ID
    assert result.session.student_id == STUDENT_ID
    assert result.session.status is ExamSessionStatus.IN_PROGRESS
    assert result.session.provider_session_id == "sess_test_123"
    assert result.session.expires_at == SECRET_EXPIRES_AT
    assert session_repository.sessions[result.session.id].exam_id == EXAM_ID
    saved_results = list(result_repository.results.values())
    assert len(saved_results) == 1
    assert saved_results[0].session_id == result.session.id
    assert saved_results[0].status is ExamResultStatus.PENDING


@pytest.mark.asyncio
async def test_start_exam_session_student_only():
    service = ExamService(
        repository=InMemoryExamRepository([make_exam()]),
        classroom_usecase=FakeClassroomUseCase(make_classroom()),
        session_repository=InMemoryExamSessionRepository(),
        result_repository=InMemoryExamResultRepository(),
        turn_repository=InMemoryExamTurnRepository(),
        realtime_session_port=FakeRealtimeSessionPort(),
    )

    with pytest.raises(AuthForbiddenException):
        await service.start_exam_session(
            exam_id=EXAM_ID,
            current_user=make_current_user(
                role=UserRole.PROFESSOR,
                user_id=PROFESSOR_ID,
            ),
        )


@pytest.mark.asyncio
async def test_start_exam_session_blocks_when_session_already_in_progress():
    in_progress_session = ExamSession.start(
        exam_id=EXAM_ID,
        student_id=STUDENT_ID,
        started_at=STARTS_AT,
        attempt_number=1,
    )
    session_repository = InMemoryExamSessionRepository()
    await session_repository.save(in_progress_session)
    service = ExamService(
        repository=InMemoryExamRepository([make_exam(max_attempts=2)]),
        classroom_usecase=FakeClassroomUseCase(make_classroom()),
        session_repository=session_repository,
        result_repository=InMemoryExamResultRepository(),
        turn_repository=InMemoryExamTurnRepository(),
        realtime_session_port=FakeRealtimeSessionPort(),
    )

    with pytest.raises(ExamSessionAlreadyInProgressException):
        await service.start_exam_session(
            exam_id=EXAM_ID,
            current_user=make_current_user(
                role=UserRole.STUDENT,
                user_id=STUDENT_ID,
            ),
        )


@pytest.mark.asyncio
async def test_start_exam_session_assigns_second_attempt_after_completion():
    completed_session = ExamSession(
        exam_id=EXAM_ID,
        student_id=STUDENT_ID,
        status=ExamSessionStatus.COMPLETED,
        started_at=STARTS_AT,
        last_activity_at=ENDS_AT,
        ended_at=ENDS_AT,
        attempt_number=1,
    )
    session_repository = InMemoryExamSessionRepository()
    await session_repository.save(completed_session)
    result_repository = InMemoryExamResultRepository()
    service = ExamService(
        repository=InMemoryExamRepository([make_exam(max_attempts=2)]),
        classroom_usecase=FakeClassroomUseCase(make_classroom()),
        session_repository=session_repository,
        result_repository=result_repository,
        turn_repository=InMemoryExamTurnRepository(),
        realtime_session_port=FakeRealtimeSessionPort(),
    )

    result = await service.start_exam_session(
        exam_id=EXAM_ID,
        current_user=make_current_user(
            role=UserRole.STUDENT,
            user_id=STUDENT_ID,
        ),
    )

    assert result.session.attempt_number == 2
    assert len(result_repository.results) == 1


@pytest.mark.asyncio
async def test_start_exam_session_blocks_when_max_attempts_exceeded():
    first_session = ExamSession(
        exam_id=EXAM_ID,
        student_id=STUDENT_ID,
        status=ExamSessionStatus.COMPLETED,
        started_at=STARTS_AT,
        last_activity_at=ENDS_AT,
        ended_at=ENDS_AT,
        attempt_number=1,
    )
    session_repository = InMemoryExamSessionRepository()
    await session_repository.save(first_session)
    service = ExamService(
        repository=InMemoryExamRepository([make_exam(max_attempts=1)]),
        classroom_usecase=FakeClassroomUseCase(make_classroom()),
        session_repository=session_repository,
        result_repository=InMemoryExamResultRepository(),
        turn_repository=InMemoryExamTurnRepository(),
        realtime_session_port=FakeRealtimeSessionPort(),
    )

    with pytest.raises(ExamSessionMaxAttemptsExceededException):
        await service.start_exam_session(
            exam_id=EXAM_ID,
            current_user=make_current_user(
                role=UserRole.STUDENT,
                user_id=STUDENT_ID,
            ),
        )


@pytest.mark.asyncio
async def test_start_exam_session_blocks_when_result_completed():
    session_repository = InMemoryExamSessionRepository()
    result_repository = InMemoryExamResultRepository()
    completed_result = ExamResult(
        exam_id=EXAM_ID,
        session_id=UUID("77777777-7777-7777-7777-777777777777"),
        student_id=STUDENT_ID,
        status=ExamResultStatus.COMPLETED,
        submitted_at=ENDS_AT,
    )
    await result_repository.save(completed_result)
    realtime_port = FakeRealtimeSessionPort()
    service = ExamService(
        repository=InMemoryExamRepository([make_exam(max_attempts=2)]),
        classroom_usecase=FakeClassroomUseCase(make_classroom()),
        session_repository=session_repository,
        result_repository=result_repository,
        turn_repository=InMemoryExamTurnRepository(),
        realtime_session_port=realtime_port,
    )

    with pytest.raises(ExamSessionUnavailableException):
        await service.start_exam_session(
            exam_id=EXAM_ID,
            current_user=make_current_user(
                role=UserRole.STUDENT,
                user_id=STUDENT_ID,
            ),
        )

    assert session_repository.sessions == {}
    assert realtime_port.calls == []


@pytest.mark.asyncio
async def test_start_exam_session_blocks_after_session_lock_race():
    result_repository = InMemoryExamResultRepository()
    session_repository = CompletedResultAppearsAfterLockSessionRepository(
        result_repository=result_repository,
    )
    realtime_port = FakeRealtimeSessionPort()
    service = ExamService(
        repository=InMemoryExamRepository([make_exam(max_attempts=2)]),
        classroom_usecase=FakeClassroomUseCase(make_classroom()),
        session_repository=session_repository,
        result_repository=result_repository,
        turn_repository=InMemoryExamTurnRepository(),
        realtime_session_port=realtime_port,
    )

    with pytest.raises(ExamSessionUnavailableException):
        await service.start_exam_session(
            exam_id=EXAM_ID,
            current_user=make_current_user(
                role=UserRole.STUDENT,
                user_id=STUDENT_ID,
            ),
        )

    assert session_repository.sessions == {}
    assert realtime_port.calls == []


@pytest.mark.asyncio
async def test_start_exam_session_blocks_during_result_lock_race():
    result_repository = CompletedResultAppearsDuringResultLockRepository()
    realtime_port = FakeRealtimeSessionPort()
    service = ExamService(
        repository=InMemoryExamRepository([make_exam(max_attempts=2)]),
        classroom_usecase=FakeClassroomUseCase(make_classroom()),
        session_repository=InMemoryExamSessionRepository(),
        result_repository=result_repository,
        turn_repository=InMemoryExamTurnRepository(),
        realtime_session_port=realtime_port,
    )

    with pytest.raises(ExamSessionUnavailableException):
        await service.start_exam_session(
            exam_id=EXAM_ID,
            current_user=make_current_user(
                role=UserRole.STUDENT,
                user_id=STUDENT_ID,
            ),
        )

    assert result_repository.completed_result_injected is True
    assert realtime_port.calls == []


@pytest.mark.asyncio
async def test_start_exam_session_does_not_persist_twice_after_secret():
    session_repository = FailOnSecondSessionSaveRepository()
    result_repository = InMemoryExamResultRepository()
    service = ExamService(
        repository=InMemoryExamRepository([make_exam(max_attempts=2)]),
        classroom_usecase=FakeClassroomUseCase(make_classroom()),
        session_repository=session_repository,
        result_repository=result_repository,
        turn_repository=InMemoryExamTurnRepository(),
        realtime_session_port=FakeRealtimeSessionPort(),
    )

    result = await service.start_exam_session(
        exam_id=EXAM_ID,
        current_user=make_current_user(
            role=UserRole.STUDENT,
            user_id=STUDENT_ID,
        ),
    )

    assert result.client_secret == "ek_test_secret"
    assert result.session.provider_session_id == "sess_test_123"
    assert result.session.expires_at == SECRET_EXPIRES_AT
    assert session_repository.save_calls == 1
    assert session_repository.sessions[
        result.session.id
    ].provider_session_id == ("sess_test_123")


@pytest.mark.asyncio
async def test_start_exam_session_maps_in_progress_integrity_error():
    session_repository = InMemoryExamSessionRepository()
    session_repository.raise_on_save = IntegrityError(
        statement=None,
        params=None,
        orig=Exception("ix_t_exam_session_single_in_progress"),
    )
    service = ExamService(
        repository=InMemoryExamRepository([make_exam(max_attempts=2)]),
        classroom_usecase=FakeClassroomUseCase(make_classroom()),
        session_repository=session_repository,
        result_repository=InMemoryExamResultRepository(),
        turn_repository=InMemoryExamTurnRepository(),
        realtime_session_port=FakeRealtimeSessionPort(),
    )

    with pytest.raises(ExamSessionAlreadyInProgressException):
        await service.start_exam_session(
            exam_id=EXAM_ID,
            current_user=make_current_user(
                role=UserRole.STUDENT,
                user_id=STUDENT_ID,
            ),
        )


@pytest.mark.asyncio
async def test_start_exam_session_skips_secret_when_save_fails():
    session_repository = InMemoryExamSessionRepository()
    session_repository.raise_on_save = IntegrityError(
        statement=None,
        params=None,
        orig=Exception("ix_t_exam_session_single_in_progress"),
    )
    service = ExamService(
        repository=InMemoryExamRepository([make_exam(max_attempts=2)]),
        classroom_usecase=FakeClassroomUseCase(make_classroom()),
        session_repository=session_repository,
        result_repository=InMemoryExamResultRepository(),
        turn_repository=InMemoryExamTurnRepository(),
        realtime_session_port=FailIfSecretCreatedRealtimeSessionPort(),
    )

    with pytest.raises(ExamSessionAlreadyInProgressException):
        await service.start_exam_session(
            exam_id=EXAM_ID,
            current_user=make_current_user(
                role=UserRole.STUDENT,
                user_id=STUDENT_ID,
            ),
        )


@pytest.mark.asyncio
async def test_start_exam_session_maps_attempt_constraint_integrity_error():
    session_repository = InMemoryExamSessionRepository()
    session_repository.raise_on_save = IntegrityError(
        statement=None,
        params=None,
        orig=Exception("uq_t_exam_session_exam_student_attempt"),
    )
    service = ExamService(
        repository=InMemoryExamRepository([make_exam(max_attempts=2)]),
        classroom_usecase=FakeClassroomUseCase(make_classroom()),
        session_repository=session_repository,
        result_repository=InMemoryExamResultRepository(),
        turn_repository=InMemoryExamTurnRepository(),
        realtime_session_port=FakeRealtimeSessionPort(),
    )

    with pytest.raises(ExamSessionMaxAttemptsExceededException):
        await service.start_exam_session(
            exam_id=EXAM_ID,
            current_user=make_current_user(
                role=UserRole.STUDENT,
                user_id=STUDENT_ID,
            ),
        )


@pytest.mark.asyncio
async def test_start_exam_session_includes_exam_context_in_instructions():
    realtime_port = FakeRealtimeSessionPort()
    service = ExamService(
        repository=InMemoryExamRepository([make_exam()]),
        classroom_usecase=FakeClassroomUseCase(make_classroom()),
        session_repository=InMemoryExamSessionRepository(),
        result_repository=InMemoryExamResultRepository(),
        turn_repository=InMemoryExamTurnRepository(),
        realtime_session_port=realtime_port,
    )

    await service.start_exam_session(
        exam_id=EXAM_ID,
        current_user=make_current_user(
            role=UserRole.STUDENT,
            user_id=STUDENT_ID,
        ),
    )

    instructions = realtime_port.calls[0]["instructions"]

    assert "중간 평가" in instructions
    assert "개념 이해" in instructions
    assert "문제 해결 과정" in instructions
    assert "70%" in instructions


@pytest.mark.asyncio
async def test_list_my_exam_results_returns_current_student_results_only():
    result_repository = InMemoryExamResultRepository()
    current_student_result = ExamResult(
        exam_id=EXAM_ID,
        session_id=UUID("77777777-7777-7777-7777-777777777777"),
        student_id=STUDENT_ID,
        status=ExamResultStatus.PENDING,
    )
    other_result = ExamResult(
        exam_id=EXAM_ID,
        session_id=UUID("88888888-8888-8888-8888-888888888888"),
        student_id=UUID("99999999-9999-9999-9999-999999999999"),
        status=ExamResultStatus.COMPLETED,
    )
    await result_repository.save(current_student_result)
    await result_repository.save(other_result)

    service = ExamService(
        repository=InMemoryExamRepository([make_exam()]),
        classroom_usecase=FakeClassroomUseCase(make_classroom()),
        session_repository=InMemoryExamSessionRepository(),
        result_repository=result_repository,
        turn_repository=InMemoryExamTurnRepository(),
        realtime_session_port=FakeRealtimeSessionPort(),
    )

    results = await service.list_my_exam_results(
        exam_id=EXAM_ID,
        current_user=make_current_user(
            role=UserRole.STUDENT,
            user_id=STUDENT_ID,
        ),
    )

    assert len(results) == 1
    assert results[0].student_id == STUDENT_ID


@pytest.mark.asyncio
async def test_record_exam_turn_saves_question_and_answer_history():
    now = datetime(2026, 4, 1, 9, 5, tzinfo=UTC)
    session_repository = InMemoryExamSessionRepository()
    turn_repository = InMemoryExamTurnRepository()
    session = ExamSession(
        exam_id=EXAM_ID,
        student_id=STUDENT_ID,
        status=ExamSessionStatus.IN_PROGRESS,
        started_at=STARTS_AT,
        last_activity_at=STARTS_AT,
        attempt_number=1,
    )
    session.id = UUID("66666666-6666-6666-6666-666666666666")
    await session_repository.save(session)

    service = ExamService(
        repository=InMemoryExamRepository([make_exam()]),
        classroom_usecase=FakeClassroomUseCase(make_classroom()),
        session_repository=session_repository,
        result_repository=InMemoryExamResultRepository(),
        turn_repository=turn_repository,
        realtime_session_port=FakeRealtimeSessionPort(),
    )

    question_turn = await service.record_exam_turn(
        exam_id=EXAM_ID,
        session_id=session.id,
        current_user=make_current_user(
            role=UserRole.STUDENT,
            user_id=STUDENT_ID,
        ),
        command=RecordExamTurnCommand(
            role=ExamTurnRole.ASSISTANT,
            event_type=ExamTurnEventType.QUESTION,
            content="머신러닝과 딥러닝의 차이를 설명해보세요.",
            metadata={"message_id": "msg-question-1"},
            occurred_at=now,
        ),
    )
    answer_turn = await service.record_exam_turn(
        exam_id=EXAM_ID,
        session_id=session.id,
        current_user=make_current_user(
            role=UserRole.STUDENT,
            user_id=STUDENT_ID,
        ),
        command=RecordExamTurnCommand(
            role=ExamTurnRole.STUDENT,
            event_type=ExamTurnEventType.ANSWER,
            content="딥러닝은 머신러닝의 하위 분야입니다.",
            metadata={"message_id": "msg-answer-1"},
            occurred_at=now,
        ),
    )

    assert question_turn.sequence == 1
    assert question_turn.event_type is ExamTurnEventType.QUESTION
    assert answer_turn.sequence == 2
    assert answer_turn.role is ExamTurnRole.STUDENT
    assert answer_turn.content == "딥러닝은 머신러닝의 하위 분야입니다."
    assert session_repository.sessions[session.id].last_activity_at == now


@pytest.mark.asyncio
async def test_record_exam_turn_rejects_other_students_session():
    session_repository = InMemoryExamSessionRepository()
    session = ExamSession(
        exam_id=EXAM_ID,
        student_id=UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"),
        status=ExamSessionStatus.IN_PROGRESS,
        started_at=STARTS_AT,
        last_activity_at=STARTS_AT,
        attempt_number=1,
    )
    session.id = UUID("66666666-6666-6666-6666-666666666666")
    await session_repository.save(session)

    service = ExamService(
        repository=InMemoryExamRepository([make_exam()]),
        classroom_usecase=FakeClassroomUseCase(make_classroom()),
        session_repository=session_repository,
        result_repository=InMemoryExamResultRepository(),
        turn_repository=InMemoryExamTurnRepository(),
        realtime_session_port=FakeRealtimeSessionPort(),
    )

    with pytest.raises(ExamSessionOwnershipForbiddenDomainException):
        await service.record_exam_turn(
            exam_id=EXAM_ID,
            session_id=session.id,
            current_user=make_current_user(
                role=UserRole.STUDENT,
                user_id=STUDENT_ID,
            ),
            command=RecordExamTurnCommand(
                role=ExamTurnRole.STUDENT,
                event_type=ExamTurnEventType.ANSWER,
                content="답변",
                metadata={},
                occurred_at=STARTS_AT,
            ),
        )


@pytest.mark.asyncio
async def test_complete_exam_session_enqueues_evaluation_job():
    now = datetime(2026, 4, 1, 10, 0, tzinfo=UTC)
    session_repository = InMemoryExamSessionRepository()
    session = ExamSession(
        exam_id=EXAM_ID,
        student_id=STUDENT_ID,
        status=ExamSessionStatus.IN_PROGRESS,
        started_at=STARTS_AT,
        last_activity_at=STARTS_AT,
        attempt_number=1,
    )
    session.id = UUID("66666666-6666-6666-6666-666666666666")
    await session_repository.save(session)
    async_job_service = FakeAsyncJobService()

    service = ExamService(
        repository=InMemoryExamRepository([make_exam()]),
        classroom_usecase=FakeClassroomUseCase(make_classroom()),
        session_repository=session_repository,
        result_repository=InMemoryExamResultRepository(),
        turn_repository=InMemoryExamTurnRepository(),
        realtime_session_port=FakeRealtimeSessionPort(),
        async_job_service=async_job_service,
    )

    completed_session = await service.complete_exam_session(
        exam_id=EXAM_ID,
        session_id=session.id,
        current_user=make_current_user(
            role=UserRole.STUDENT,
            user_id=STUDENT_ID,
        ),
        command=CompleteExamSessionCommand(occurred_at=now),
    )

    assert completed_session.status is ExamSessionStatus.COMPLETED
    assert completed_session.ended_at == now
    assert session_repository.sessions[session.id].last_activity_at == now
    assert len(async_job_service.enqueue_calls) == 1
    enqueue_call = async_job_service.enqueue_calls[0]
    assert enqueue_call["job_type"] is AsyncJobType.EXAM_RESULT_EVALUATION
    assert enqueue_call["target_type"] is AsyncJobTargetType.EXAM
    assert enqueue_call["target_id"] == EXAM_ID
    assert enqueue_call["requested_by"] == STUDENT_ID
    assert enqueue_call["dedupe_key"] == f"exam-result-evaluation:{session.id}"
    assert enqueue_call["payload"] == {
        "exam_id": str(EXAM_ID),
        "session_id": str(session.id),
        "student_id": str(STUDENT_ID),
    }


@pytest.mark.asyncio
async def test_finalize_exam_result_updates_pending_result():
    now = datetime(2026, 4, 1, 10, 1, tzinfo=UTC)
    session_repository = InMemoryExamSessionRepository()
    result_repository = InMemoryExamResultRepository()
    session = ExamSession(
        exam_id=EXAM_ID,
        student_id=STUDENT_ID,
        status=ExamSessionStatus.COMPLETED,
        started_at=STARTS_AT,
        last_activity_at=ENDS_AT,
        ended_at=ENDS_AT,
        attempt_number=1,
    )
    session.id = UUID("66666666-6666-6666-6666-666666666666")
    await session_repository.save(session)
    pending_result = ExamResult(
        exam_id=EXAM_ID,
        session_id=session.id,
        student_id=STUDENT_ID,
        status=ExamResultStatus.PENDING,
    )
    await result_repository.save(pending_result)

    service = ExamService(
        repository=InMemoryExamRepository([make_exam()]),
        classroom_usecase=FakeClassroomUseCase(make_classroom()),
        session_repository=session_repository,
        result_repository=result_repository,
        turn_repository=InMemoryExamTurnRepository(),
        realtime_session_port=FakeRealtimeSessionPort(),
    )

    result = await service.finalize_exam_result(
        exam_id=EXAM_ID,
        session_id=session.id,
        current_user=make_current_user(
            role=UserRole.STUDENT,
            user_id=STUDENT_ID,
        ),
        command=FinalizeExamResultCommand(
            occurred_at=now,
        ),
    )

    assert result.status is ExamResultStatus.PENDING
    assert result.overall_score is None
    assert result.submitted_at is None
    assert result.summary is None
