from collections.abc import Sequence
from datetime import UTC, datetime
from uuid import UUID

import pytest

from app.auth.application.exception import AuthForbiddenException
from app.auth.domain.entity import CurrentUser
from app.classroom.domain.entity import Classroom
from app.classroom.domain.usecase import ClassroomUseCase
from app.exam.application.exception import ExamNotFoundException
from app.exam.application.service import ExamService
from app.exam.domain.command import CreateExamCommand, ExamCriterionCommand
from app.exam.domain.entity.exam import ExamCriterion
from app.exam.domain.entity import (
    Exam,
    ExamCriterion,
    ExamResult,
    ExamResultStatus,
    ExamSession,
    ExamSessionStatus,
    ExamStatus,
    ExamTurn,
    ExamType,
    RealtimeClientSecret,
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
SESSION_ID = UUID("66666666-6666-6666-6666-666666666666")
STARTS_AT = datetime(2026, 4, 1, 9, 0, tzinfo=UTC)
ENDS_AT = datetime(2026, 4, 1, 10, 0, tzinfo=UTC)


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

    async def save(self, entity: ExamSession) -> None:
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
        self.instructions: list[str] = []

    async def create_client_secret(
        self,
        *,
        instructions: str,
    ) -> RealtimeClientSecret:
        self.instructions.append(instructions)
        return RealtimeClientSecret(
            value="secret-value",
            expires_at=ENDS_AT,
            provider_session_id="rt-session-1",
        )


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
    ):
        _ = current_user
        if classroom_id != self.classroom.id:
            raise AuthForbiddenException()
        return self.classroom

    async def get_manageable_classroom(
        self,
        *,
        classroom_id: UUID,
        current_user: CurrentUser,
    ):
        return await self.get_classroom(
            classroom_id=classroom_id,
            current_user=current_user,
        )

    async def list_classrooms(
        self, *, current_user: CurrentUser
    ) -> list[Classroom]:
        raise NotImplementedError

    async def update_classroom(
        self,
        *,
        classroom_id,
        current_user,
        command,
    ) -> Classroom:
        raise NotImplementedError

    async def delete_classroom(
        self, *, classroom_id, current_user
    ) -> Classroom:
        raise NotImplementedError

    async def remove_classroom_student(
        self,
        *,
        classroom_id,
        current_user,
        command,
    ) -> Classroom:
        raise NotImplementedError

    async def invite_classroom_students(
        self,
        *,
        classroom_id,
        current_user,
        command,
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


def make_exam(*, classroom_id: UUID = CLASSROOM_ID) -> Exam:
    exam = Exam(
        classroom_id=classroom_id,
        title="중간 평가",
        description="1주차 범위 평가",
        exam_type=ExamType.MIDTERM,
        status=ExamStatus.READY,
        duration_minutes=60,
        starts_at=STARTS_AT,
        ends_at=ENDS_AT,
        allow_retake=False,
        criteria=[
            ExamCriterion(
                exam_id=EXAM_ID,
                title="개념 이해",
                description="핵심 개념을 정확히 설명하는지 평가",
                weight=60,
                sort_order=1,
                excellent_definition="핵심 개념과 관계를 정확히 설명한다.",
                average_definition=(
                    "핵심 개념은 설명하지만 일부 연결이 부족하다."
                ),
                poor_definition="핵심 개념 설명이 부정확하다.",
            )
        ],
    )
    exam.id = EXAM_ID
    return exam


def make_current_user(
    *,
    role: UserRole,
    user_id: UUID,
) -> CurrentUser:
    return CurrentUser(
        id=user_id,
        organization_id=ORG_ID,
        login_id="user01",
        role=role,
    )


def build_service(*, exams: list[Exam] | None = None):
    session_repository = InMemoryExamSessionRepository()
    result_repository = InMemoryExamResultRepository()
    turn_repository = InMemoryExamTurnRepository()
    realtime_port = FakeRealtimeSessionPort()
    service = ExamService(
        repository=InMemoryExamRepository(exams),
        classroom_usecase=FakeClassroomUseCase(make_classroom()),
        session_repository=session_repository,
        result_repository=result_repository,
        turn_repository=turn_repository,
        realtime_session_port=realtime_port,
    )
    return (
        service,
        session_repository,
        result_repository,
        turn_repository,
        realtime_port,
    )


def test_exam_create_builds_criteria_with_generated_exam_id():
    criteria = [
        ExamCriterion(
            exam_id=UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"),
            title="개념 이해",
            description="핵심 개념을 정확히 설명하는지 평가",
            weight=100,
            sort_order=1,
            excellent_definition="정확히 설명한다.",
            average_definition="대체로 설명한다.",
            poor_definition="설명이 부정확하다.",
        )
    ]

    exam = Exam.create(
        classroom_id=CLASSROOM_ID,
        title="중간 평가",
        description="1주차 범위 평가",
        exam_type=ExamType.MIDTERM,
        duration_minutes=60,
        starts_at=STARTS_AT,
        ends_at=ENDS_AT,
        allow_retake=False,
        criteria=criteria,
    )

    assert len(exam.criteria) == 1
    assert exam.criteria[0].exam_id == exam.id
    assert exam.criteria[0].title == "개념 이해"
    assert exam.belongs_to_classroom(CLASSROOM_ID) is True


@pytest.mark.asyncio
async def test_create_exam_success():
    service, _, _, _, _ = build_service()

    exam = await service.create_exam(
        classroom_id=CLASSROOM_ID,
        current_user=make_current_user(
            role=UserRole.PROFESSOR,
            user_id=PROFESSOR_ID,
        ),
        command=CreateExamCommand(
            title="중간 평가",
            description="1주차 범위 평가",
            exam_type=ExamType.MIDTERM,
            duration_minutes=60,
            starts_at=STARTS_AT,
            ends_at=ENDS_AT,
            allow_retake=False,
            criteria=[
                ExamCriterionCommand(
                    title="개념 이해",
                    description="핵심 개념을 정확히 설명하는지 평가",
                    weight=60,
                    sort_order=1,
                    excellent_definition="핵심 개념과 관계를 정확히 설명한다.",
                    average_definition=(
                        "핵심 개념은 설명하지만 일부 연결이 부족하다."
                    ),
                    poor_definition="핵심 개념 설명이 부정확하다.",
                ),
                ExamCriterionCommand(
                    title="문제 해결 과정",
                    description="풀이 근거와 절차를 평가",
                    weight=40,
                    sort_order=2,
                    excellent_definition="근거와 절차가 명확하다.",
                    average_definition="주요 절차는 맞지만 근거가 부족하다.",
                    poor_definition="풀이 근거와 절차가 불분명하다.",
                ),
            ],
        ),
    )

    assert exam.classroom_id == CLASSROOM_ID
    assert exam.title == "중간 평가"
    assert exam.description == "1주차 범위 평가"
    assert exam.exam_type is ExamType.MIDTERM
    assert exam.status is ExamStatus.READY
    assert exam.duration_minutes == 60
    assert exam.starts_at == STARTS_AT
    assert exam.ends_at == ENDS_AT
    assert exam.allow_retake is False
    assert len(exam.criteria) == 2
    assert exam.criteria[0].title == "개념 이해"
    assert exam.criteria[1].weight == 40
    instructions = exam.build_realtime_instructions()
    assert "시험 제목: 중간 평가" in instructions
    assert "- 2. 문제 해결 과정 (40%)" in instructions


@pytest.mark.asyncio
async def test_create_exam_student_forbidden():
    service, _, _, _, _ = build_service()

    with pytest.raises(AuthForbiddenException):
        await service.create_exam(
            classroom_id=CLASSROOM_ID,
            current_user=make_current_user(
                role=UserRole.STUDENT,
                user_id=STUDENT_ID,
            ),
            command=CreateExamCommand(
                title="중간 평가",
                description="1주차 범위 평가",
                exam_type=ExamType.MIDTERM,
                duration_minutes=60,
                starts_at=STARTS_AT,
                ends_at=ENDS_AT,
                allow_retake=False,
                criteria=[
                    ExamCriterionCommand(
                        title="개념 이해",
                        description="핵심 개념을 정확히 설명하는지 평가",
                        weight=100,
                        sort_order=1,
                        excellent_definition=None,
                        average_definition=None,
                        poor_definition=None,
                    )
                ],
            ),
        )


@pytest.mark.asyncio
async def test_list_exams_returns_classroom_exams():
    service, _, _, _, _ = build_service(exams=[make_exam()])

    exams = await service.list_exams(
        classroom_id=CLASSROOM_ID,
        current_user=make_current_user(
            role=UserRole.STUDENT,
            user_id=STUDENT_ID,
        ),
    )

    assert len(exams) == 1
    assert exams[0].title == "중간 평가"
    assert exams[0].criteria[0].title == "개념 이해"
    assert exams[0].status is ExamStatus.READY


@pytest.mark.asyncio
async def test_get_exam_from_other_classroom_raises_not_found():
    service, _, _, _, _ = build_service(
        exams=[
            make_exam(classroom_id=UUID("77777777-7777-7777-7777-777777777777"))
        ]
    )

    with pytest.raises(ExamNotFoundException):
        await service.get_exam(
            classroom_id=CLASSROOM_ID,
            exam_id=EXAM_ID,
            current_user=make_current_user(
                role=UserRole.PROFESSOR,
                user_id=PROFESSOR_ID,
            ),
        )


@pytest.mark.asyncio
async def test_get_exam_returns_operational_fields_and_criteria():
    service, _, _, _, _ = build_service(exams=[make_exam()])

    exam = await service.get_exam(
        classroom_id=CLASSROOM_ID,
        exam_id=EXAM_ID,
        current_user=make_current_user(
            role=UserRole.STUDENT,
            user_id=STUDENT_ID,
        ),
    )

    assert exam.exam_type is ExamType.MIDTERM
    assert exam.status is ExamStatus.READY
    assert exam.duration_minutes == 60
    assert exam.allow_retake is False
    assert exam.criteria[0].excellent_definition == (
        "핵심 개념과 관계를 정확히 설명한다."
    )


@pytest.mark.asyncio
async def test_start_exam_session_returns_client_secret_and_session():
    service, session_repository, result_repository, _, realtime_port = (
        build_service(exams=[make_exam()])
    )

    result = await service.start_exam_session(
        exam_id=EXAM_ID,
        current_user=make_current_user(
            role=UserRole.STUDENT,
            user_id=STUDENT_ID,
        ),
    )

    saved_sessions = list(session_repository.sessions.values())
    assert len(saved_sessions) == 1
    session = saved_sessions[0]
    assert result.client_secret == "secret-value"
    assert result.session.id == session.id
    assert session.exam_id == EXAM_ID
    assert session.student_id == STUDENT_ID
    assert session.status is ExamSessionStatus.IN_PROGRESS
    assert session.provider_session_id == "rt-session-1"
    saved_results = list(result_repository.results.values())
    assert len(saved_results) == 1
    assert saved_results[0].status is ExamResultStatus.PENDING
    assert realtime_port.instructions
    assert "개념 이해" in realtime_port.instructions[0]


@pytest.mark.asyncio
async def test_start_exam_session_professor_forbidden():
    service, _, _, _, _ = build_service(exams=[make_exam()])

    with pytest.raises(AuthForbiddenException):
        await service.start_exam_session(
            exam_id=EXAM_ID,
            current_user=make_current_user(
                role=UserRole.PROFESSOR,
                user_id=PROFESSOR_ID,
            ),
        )
