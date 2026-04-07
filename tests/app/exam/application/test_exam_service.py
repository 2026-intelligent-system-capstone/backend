from collections.abc import Sequence
from datetime import UTC, datetime
from uuid import UUID

import pytest

from app.auth.application.exception import AuthForbiddenException
from app.auth.domain.entity import CurrentUser
from app.classroom.domain.entity import (
    Classroom,
    ClassroomMaterialIngestStatus,
)
from app.classroom.domain.usecase import ClassroomUseCase
from app.exam.application.exception import (
    ExamNotFoundException,
    ExamQuestionGenerationContextUnavailableException,
    ExamQuestionGenerationFailedException,
    ExamQuestionGenerationMaterialIngestFailedException,
    ExamQuestionGenerationMaterialNotFoundException,
    ExamQuestionGenerationMaterialNotReadyException,
    ExamQuestionGenerationUnavailableException,
    ExamQuestionNotFoundException,
)
from app.exam.application.service import ExamService
from app.exam.domain.command import (
    CreateExamCommand,
    CreateExamQuestionCommand,
    ExamCriterionCommand,
    ExamQuestionBloomCountCommand,
    GenerateExamQuestionsCommand,
    UpdateExamQuestionCommand,
)
from app.exam.domain.entity import (
    BloomLevel,
    Exam,
    ExamCriterion,
    ExamDifficulty,
    ExamQuestionStatus,
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
from app.exam.domain.service import (
    ExamQuestionGenerationPort,
    GeneratedExamQuestionDraft,
    RealtimeSessionPort,
)
from app.user.domain.entity import UserRole

ORG_ID = UUID("11111111-1111-1111-1111-111111111111")
CLASSROOM_ID = UUID("22222222-2222-2222-2222-222222222222")
EXAM_ID = UUID("33333333-3333-3333-3333-333333333333")
PROFESSOR_ID = UUID("44444444-4444-4444-4444-444444444444")
STUDENT_ID = UUID("55555555-5555-5555-5555-555555555555")
SESSION_ID = UUID("66666666-6666-6666-6666-666666666666")
STARTS_AT = datetime(2026, 4, 1, 9, 0, tzinfo=UTC)
ENDS_AT = datetime(2026, 4, 1, 10, 0, tzinfo=UTC)
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


class FakeExamQuestionGenerationPort(ExamQuestionGenerationPort):
    def __init__(
        self,
        drafts: Sequence[GeneratedExamQuestionDraft] | None = None,
    ):
        self.drafts = list(drafts or [])
        self.requests = []

    async def generate_questions(self, *, request):
        self.requests.append(request)
        return list(self.drafts)


class FakeClassroomUseCase(ClassroomUseCase):
    def __init__(
        self,
        classroom: Classroom,
        materials: list | None = None,
    ):
        self.classroom = classroom
        self.materials = list(materials or [])

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
        _ = current_user
        if classroom_id != self.classroom.id:
            raise AuthForbiddenException()
        return list(self.materials)

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


def make_exam(
    *,
    classroom_id: UUID = CLASSROOM_ID,
    week: int = WEEK,
    exam_type: ExamType = ExamType.MIDTERM,
    title: str = "중간 평가",
) -> Exam:
    exam = Exam(
        classroom_id=classroom_id,
        title=title,
        description="1주차 범위 평가",
        exam_type=exam_type,
        status=ExamStatus.READY,
        duration_minutes=60,
        starts_at=STARTS_AT,
        ends_at=ENDS_AT,
        allow_retake=False,
        week=week,
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


def make_question_command() -> CreateExamQuestionCommand:
    return CreateExamQuestionCommand(
        question_number=1,
        bloom_level=BloomLevel.APPLY,
        difficulty=ExamDifficulty.MEDIUM,
        question_text="회귀와 분류의 차이를 설명하세요.",
        scope_text="1주차 머신러닝 기초",
        evaluation_objective="학습자가 지도학습의 핵심 구분을 이해하는지 평가",
        answer_key="지도학습 목적과 출력 형태 차이를 포함해야 한다.",
        scoring_criteria="핵심 개념과 예시를 함께 설명하면 정답",
        source_material_ids=[
            UUID("99999999-9999-9999-9999-999999999999")
        ],
    )


def make_material_result(
    *,
    material_id: UUID,
    ingest_status: ClassroomMaterialIngestStatus = (
        ClassroomMaterialIngestStatus.COMPLETED
    ),
):
    file = type("File", (), {})()
    file.file_name = "week1.pdf"

    material = type("Material", (), {})()
    material.id = material_id
    material.title = "1주차 자료"
    material.week = 1
    material.ingest_status = ingest_status

    result = type("MaterialResult", (), {})()
    result.material = material
    result.file = file
    return result


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


def build_service(
    *,
    exams: list[Exam] | None = None,
    materials: list | None = None,
    question_generation_port: FakeExamQuestionGenerationPort | None = None,
):
    session_repository = InMemoryExamSessionRepository()
    result_repository = InMemoryExamResultRepository()
    turn_repository = InMemoryExamTurnRepository()
    realtime_port = FakeRealtimeSessionPort()
    generation_port = question_generation_port
    service = ExamService(
        repository=InMemoryExamRepository(exams),
        classroom_usecase=FakeClassroomUseCase(
            make_classroom(),
            materials=materials,
        ),
        session_repository=session_repository,
        result_repository=result_repository,
        turn_repository=turn_repository,
        realtime_session_port=realtime_port,
        question_generation_port=generation_port,
    )
    return (
        service,
        session_repository,
        result_repository,
        turn_repository,
        realtime_port,
        generation_port,
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
        week=WEEK,
        criteria=criteria,
    )

    assert len(exam.criteria) == 1
    assert type(exam.id) is UUID
    assert type(exam.criteria[0].id) is UUID
    assert type(exam.criteria[0].exam_id) is UUID
    assert exam.criteria[0].exam_id == exam.id
    assert exam.criteria[0].title == "개념 이해"
    assert exam.week == WEEK
    assert exam.belongs_to_classroom(CLASSROOM_ID) is True


@pytest.mark.asyncio
async def test_create_exam_success():
    service, _, _, _, _, _ = build_service()

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
        week=WEEK,
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
    assert exam.week == WEEK
    assert len(exam.criteria) == 2
    assert exam.criteria[0].title == "개념 이해"
    assert exam.criteria[1].weight == 40
    assert exam.week == WEEK
    instructions = exam.build_realtime_instructions()
    assert "시험 제목: 중간 평가" in instructions
    assert "시험 유형: midterm" in instructions
    assert "- 2. 문제 해결 과정 (40%)" in instructions


def test_exam_build_realtime_instructions_uses_weekly_type_value():
    exam = make_exam(exam_type=ExamType.WEEKLY, title="주간 평가")

    instructions = exam.build_realtime_instructions()

    assert "시험 유형: weekly" in instructions


def test_exam_build_realtime_instructions_uses_project_type_value():
    exam = make_exam(exam_type=ExamType.PROJECT, title="프로젝트 평가")

    instructions = exam.build_realtime_instructions()

    assert "시험 유형: project" in instructions


def test_create_exam_command_requires_positive_week():
    with pytest.raises(ValueError, match="greater than or equal to 1"):
        CreateExamCommand(
            title="중간 평가",
            description="1주차 범위 평가",
            exam_type=ExamType.MIDTERM,
            duration_minutes=60,
            starts_at=STARTS_AT,
            ends_at=ENDS_AT,
            allow_retake=False,
            week=0,
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
        )


@pytest.mark.asyncio
async def test_create_exam_student_forbidden():
    service, _, _, _, _, _ = build_service()

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
        week=WEEK,
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
    service, _, _, _, _, _ = build_service(exams=[make_exam()])

    exams = await service.list_exams(
        classroom_id=CLASSROOM_ID,
        current_user=make_current_user(
            role=UserRole.STUDENT,
            user_id=STUDENT_ID,
        ),
    )

    assert len(exams) == 1
    assert exams[0].title == "중간 평가"
    assert exams[0].week == WEEK
    assert exams[0].criteria[0].title == "개념 이해"
    assert exams[0].status is ExamStatus.READY


@pytest.mark.asyncio
async def test_get_exam_from_other_classroom_raises_not_found():
    service, _, _, _, _, _ = build_service(
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
    service, _, _, _, _, _ = build_service(exams=[make_exam()])

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
    assert exam.week == WEEK
    assert exam.allow_retake is False
    assert exam.criteria[0].excellent_definition == (
        "핵심 개념과 관계를 정확히 설명한다."
    )


@pytest.mark.asyncio
async def test_create_exam_question_success():
    service, _, _, _, _, _ = build_service(exams=[make_exam()])

    question = await service.create_exam_question(
        classroom_id=CLASSROOM_ID,
        exam_id=EXAM_ID,
        current_user=make_current_user(
            role=UserRole.PROFESSOR,
            user_id=PROFESSOR_ID,
        ),
        command=make_question_command(),
    )

    assert question.exam_id == EXAM_ID
    assert question.question_number == 1
    assert question.bloom_level is BloomLevel.APPLY
    assert question.difficulty is ExamDifficulty.MEDIUM
    assert question.status is ExamQuestionStatus.GENERATED


@pytest.mark.asyncio
async def test_update_exam_question_marks_reviewed():
    exam = make_exam()
    created = exam.add_question(**make_question_command().model_dump())
    service, _, _, _, _, _ = build_service(exams=[exam])

    question = await service.update_exam_question(
        classroom_id=CLASSROOM_ID,
        exam_id=EXAM_ID,
        question_id=created.id,
        current_user=make_current_user(
            role=UserRole.PROFESSOR,
            user_id=PROFESSOR_ID,
        ),
        command=UpdateExamQuestionCommand(
            question_text="수정된 질문",
            scope_text="수정 범위",
        ),
    )

    assert question.question_text == "수정된 질문"
    assert question.scope_text == "수정 범위"
    assert question.status is ExamQuestionStatus.REVIEWED


@pytest.mark.asyncio
async def test_delete_exam_question_marks_deleted():
    exam = make_exam()
    created = exam.add_question(**make_question_command().model_dump())
    service, _, _, _, _, _ = build_service(exams=[exam])

    question = await service.delete_exam_question(
        classroom_id=CLASSROOM_ID,
        exam_id=EXAM_ID,
        question_id=created.id,
        current_user=make_current_user(
            role=UserRole.PROFESSOR,
            user_id=PROFESSOR_ID,
        ),
    )

    assert question.id == created.id
    assert question.status is ExamQuestionStatus.DELETED


@pytest.mark.asyncio
async def test_update_exam_question_not_found_raises():
    service, _, _, _, _, _ = build_service(exams=[make_exam()])

    with pytest.raises(ExamQuestionNotFoundException):
        await service.update_exam_question(
            classroom_id=CLASSROOM_ID,
            exam_id=EXAM_ID,
            question_id=UUID("77777777-7777-7777-7777-777777777777"),
            current_user=make_current_user(
                role=UserRole.PROFESSOR,
                user_id=PROFESSOR_ID,
            ),
            command=UpdateExamQuestionCommand(question_text="수정"),
        )


@pytest.mark.asyncio
async def test_delete_exam_question_not_found_raises():
    service, _, _, _, _, _ = build_service(exams=[make_exam()])

    with pytest.raises(ExamQuestionNotFoundException):
        await service.delete_exam_question(
            classroom_id=CLASSROOM_ID,
            exam_id=EXAM_ID,
            question_id=UUID("77777777-7777-7777-7777-777777777777"),
            current_user=make_current_user(
                role=UserRole.PROFESSOR,
                user_id=PROFESSOR_ID,
            ),
        )


@pytest.mark.asyncio
async def test_create_exam_question_student_forbidden():
    service, _, _, _, _, _ = build_service(exams=[make_exam()])

    with pytest.raises(AuthForbiddenException):
        await service.create_exam_question(
            classroom_id=CLASSROOM_ID,
            exam_id=EXAM_ID,
            current_user=make_current_user(
                role=UserRole.STUDENT,
                user_id=STUDENT_ID,
            ),
            command=make_question_command(),
        )


@pytest.mark.asyncio
async def test_start_exam_session_returns_client_secret_and_session():
    service, session_repository, result_repository, _, realtime_port, _ = (
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
    service, _, _, _, _, _ = build_service(exams=[make_exam()])

    with pytest.raises(AuthForbiddenException):
        await service.start_exam_session(
            exam_id=EXAM_ID,
            current_user=make_current_user(
                role=UserRole.PROFESSOR,
                user_id=PROFESSOR_ID,
            ),
        )


@pytest.mark.asyncio
async def test_generate_exam_questions_success():
    material_id = UUID("99999999-9999-9999-9999-999999999999")
    generation_port = FakeExamQuestionGenerationPort(
        drafts=[
            GeneratedExamQuestionDraft(
                question_number=1,
                bloom_level=BloomLevel.APPLY,
                difficulty=ExamDifficulty.MEDIUM,
                question_text="회귀와 분류의 차이를 설명하세요.",
                scope_text="1주차 머신러닝 기초",
                evaluation_objective="지도학습 핵심 구분 평가",
                answer_key="출력 형태와 문제 목적 차이를 포함해야 한다.",
                scoring_criteria="핵심 개념과 예시 포함",
                source_material_ids=[material_id],
            )
        ]
    )
    service, _, _, _, _, _ = build_service(
        exams=[make_exam()],
        materials=[make_material_result(material_id=material_id)],
        question_generation_port=generation_port,
    )

    questions = await service.generate_exam_questions(
        classroom_id=CLASSROOM_ID,
        exam_id=EXAM_ID,
        current_user=make_current_user(
            role=UserRole.PROFESSOR,
            user_id=PROFESSOR_ID,
        ),
        command=GenerateExamQuestionsCommand(
            scope_text="1주차 머신러닝 기초",
            max_follow_ups=2,
            difficulty=ExamDifficulty.MEDIUM,
            source_material_ids=[material_id],
            bloom_counts=[
                ExamQuestionBloomCountCommand(
                    bloom_level=BloomLevel.APPLY,
                    count=1,
                )
            ],
        ),
    )

    assert len(questions) == 1
    assert questions[0].question_number == 1
    assert questions[0].status is ExamQuestionStatus.GENERATED
    assert questions[0].source_material_ids == [material_id]
    assert len(generation_port.requests) == 1
    request = generation_port.requests[0]
    assert request.scope_text == "1주차 머신러닝 기초"
    assert request.total_questions == 1
    assert request.max_follow_ups == 2
    assert request.bloom_counts[0].bloom_level is BloomLevel.APPLY
    assert request.bloom_counts[0].count == 1
    assert request.source_materials[0].material_id == material_id
    assert request.criteria[0].title == "개념 이해"


@pytest.mark.asyncio
async def test_generate_exam_questions_appends_after_existing_questions():
    material_id = UUID("99999999-9999-9999-9999-999999999999")
    exam = make_exam()
    exam.add_question(**make_question_command().model_dump())
    generation_port = FakeExamQuestionGenerationPort(
        drafts=[
            GeneratedExamQuestionDraft(
                question_number=1,
                bloom_level=BloomLevel.ANALYZE,
                difficulty=ExamDifficulty.MEDIUM,
                question_text="지도학습과 비지도학습의 차이를 비교해주세요.",
                scope_text="1주차 머신러닝 기초",
                evaluation_objective="학습 방식 차이 분석 능력 평가",
                answer_key="정답 데이터 유무와 활용 사례 차이를 설명해야 한다.",
                scoring_criteria="핵심 비교 기준을 2개 이상 제시하면 정답",
                source_material_ids=[material_id],
            )
        ]
    )
    service, _, _, _, _, _ = build_service(
        exams=[exam],
        materials=[make_material_result(material_id=material_id)],
        question_generation_port=generation_port,
    )

    questions = await service.generate_exam_questions(
        classroom_id=CLASSROOM_ID,
        exam_id=EXAM_ID,
        current_user=make_current_user(
            role=UserRole.PROFESSOR,
            user_id=PROFESSOR_ID,
        ),
        command=GenerateExamQuestionsCommand(
            scope_text="1주차 머신러닝 기초",
            max_follow_ups=0,
            difficulty=ExamDifficulty.MEDIUM,
            source_material_ids=[material_id],
            bloom_counts=[
                ExamQuestionBloomCountCommand(
                    bloom_level=BloomLevel.ANALYZE,
                    count=1,
                )
            ],
        ),
    )

    assert questions[0].question_number == 2


@pytest.mark.asyncio
async def test_generate_exam_questions_invalid_material_raises():
    service, _, _, _, _, _ = build_service(
        exams=[make_exam()],
        materials=[],
        question_generation_port=FakeExamQuestionGenerationPort(drafts=[]),
    )

    with pytest.raises(ExamQuestionGenerationMaterialNotFoundException):
        await service.generate_exam_questions(
            classroom_id=CLASSROOM_ID,
            exam_id=EXAM_ID,
            current_user=make_current_user(
                role=UserRole.PROFESSOR,
                user_id=PROFESSOR_ID,
            ),
            command=GenerateExamQuestionsCommand(
                scope_text="1주차 머신러닝 기초",
                max_follow_ups=0,
                difficulty=ExamDifficulty.MEDIUM,
                source_material_ids=[
                    UUID("99999999-9999-9999-9999-999999999999")
                ],
                bloom_counts=[
                    ExamQuestionBloomCountCommand(
                        bloom_level=BloomLevel.APPLY,
                        count=1,
                    )
                ],
            ),
        )


@pytest.mark.asyncio
async def test_generate_exam_questions_pending_material_raises():
    material_id = UUID("99999999-9999-9999-9999-999999999999")
    generation_port = FakeExamQuestionGenerationPort(drafts=[])
    service, _, _, _, _, _ = build_service(
        exams=[make_exam()],
        materials=[
            make_material_result(
                material_id=material_id,
                ingest_status=ClassroomMaterialIngestStatus.PENDING,
            )
        ],
        question_generation_port=generation_port,
    )

    with pytest.raises(ExamQuestionGenerationMaterialNotReadyException):
        await service.generate_exam_questions(
            classroom_id=CLASSROOM_ID,
            exam_id=EXAM_ID,
            current_user=make_current_user(
                role=UserRole.PROFESSOR,
                user_id=PROFESSOR_ID,
            ),
            command=GenerateExamQuestionsCommand(
                scope_text="1주차 머신러닝 기초",
                max_follow_ups=0,
                difficulty=ExamDifficulty.MEDIUM,
                source_material_ids=[material_id],
                bloom_counts=[
                    ExamQuestionBloomCountCommand(
                        bloom_level=BloomLevel.APPLY,
                        count=1,
                    )
                ],
            ),
        )

    assert generation_port.requests == []


@pytest.mark.asyncio
async def test_generate_exam_questions_failed_material_raises_before_generation(
):
    material_id = UUID("99999999-9999-9999-9999-999999999999")
    generation_port = FakeExamQuestionGenerationPort(drafts=[])
    service, _, _, _, _, _ = build_service(
        exams=[make_exam()],
        materials=[
            make_material_result(
                material_id=material_id,
                ingest_status=ClassroomMaterialIngestStatus.FAILED,
            )
        ],
        question_generation_port=generation_port,
    )

    with pytest.raises(ExamQuestionGenerationMaterialIngestFailedException):
        await service.generate_exam_questions(
            classroom_id=CLASSROOM_ID,
            exam_id=EXAM_ID,
            current_user=make_current_user(
                role=UserRole.PROFESSOR,
                user_id=PROFESSOR_ID,
            ),
            command=GenerateExamQuestionsCommand(
                scope_text="1주차 머신러닝 기초",
                max_follow_ups=0,
                difficulty=ExamDifficulty.MEDIUM,
                source_material_ids=[material_id],
                bloom_counts=[
                    ExamQuestionBloomCountCommand(
                        bloom_level=BloomLevel.APPLY,
                        count=1,
                    )
                ],
            ),
        )

    assert generation_port.requests == []


@pytest.mark.asyncio
async def test_generate_exam_questions_failed_exception_propagates():
    class FailingExamQuestionGenerationPort(ExamQuestionGenerationPort):
        async def generate_questions(self, *, request):
            _ = request
            raise ExamQuestionGenerationFailedException()

    service, _, _, _, _, _ = build_service(
        exams=[make_exam()],
        question_generation_port=FailingExamQuestionGenerationPort(),
    )

    with pytest.raises(ExamQuestionGenerationFailedException):
        await service.generate_exam_questions(
            classroom_id=CLASSROOM_ID,
            exam_id=EXAM_ID,
            current_user=make_current_user(
                role=UserRole.PROFESSOR,
                user_id=PROFESSOR_ID,
            ),
            command=GenerateExamQuestionsCommand(
                scope_text="1주차 머신러닝 기초",
                max_follow_ups=0,
                difficulty=ExamDifficulty.MEDIUM,
                source_material_ids=[],
                bloom_counts=[
                    ExamQuestionBloomCountCommand(
                        bloom_level=BloomLevel.APPLY,
                        count=1,
                    )
                ],
            ),
        )


@pytest.mark.asyncio
async def test_generate_exam_questions_context_unavailable_propagates():
    class FailingExamQuestionGenerationPort(ExamQuestionGenerationPort):
        async def generate_questions(self, *, request):
            _ = request
            raise ExamQuestionGenerationContextUnavailableException()

    service, _, _, _, _, _ = build_service(
        exams=[make_exam()],
        question_generation_port=FailingExamQuestionGenerationPort(),
    )

    with pytest.raises(ExamQuestionGenerationContextUnavailableException):
        await service.generate_exam_questions(
            classroom_id=CLASSROOM_ID,
            exam_id=EXAM_ID,
            current_user=make_current_user(
                role=UserRole.PROFESSOR,
                user_id=PROFESSOR_ID,
            ),
            command=GenerateExamQuestionsCommand(
                scope_text="1주차 머신러닝 기초",
                max_follow_ups=0,
                difficulty=ExamDifficulty.MEDIUM,
                source_material_ids=[],
                bloom_counts=[
                    ExamQuestionBloomCountCommand(
                        bloom_level=BloomLevel.APPLY,
                        count=1,
                    )
                ],
            ),
        )


@pytest.mark.asyncio
async def test_generate_exam_questions_unexpected_error_propagates():
    class FailingExamQuestionGenerationPort(ExamQuestionGenerationPort):
        async def generate_questions(self, *, request):
            _ = request
            raise RuntimeError("unexpected generation error")

    service, _, _, _, _, _ = build_service(
        exams=[make_exam()],
        question_generation_port=FailingExamQuestionGenerationPort(),
    )

    with pytest.raises(RuntimeError, match="unexpected generation error"):
        await service.generate_exam_questions(
            classroom_id=CLASSROOM_ID,
            exam_id=EXAM_ID,
            current_user=make_current_user(
                role=UserRole.PROFESSOR,
                user_id=PROFESSOR_ID,
            ),
            command=GenerateExamQuestionsCommand(
                scope_text="1주차 머신러닝 기초",
                max_follow_ups=0,
                difficulty=ExamDifficulty.MEDIUM,
                source_material_ids=[],
                bloom_counts=[
                    ExamQuestionBloomCountCommand(
                        bloom_level=BloomLevel.APPLY,
                        count=1,
                    )
                ],
            ),
        )


@pytest.mark.asyncio
async def test_generate_exam_questions_unavailable_raises():
    service, _, _, _, _, _ = build_service(exams=[make_exam()])

    with pytest.raises(ExamQuestionGenerationUnavailableException):
        await service.generate_exam_questions(
            classroom_id=CLASSROOM_ID,
            exam_id=EXAM_ID,
            current_user=make_current_user(
                role=UserRole.PROFESSOR,
                user_id=PROFESSOR_ID,
            ),
            command=GenerateExamQuestionsCommand(
                scope_text="1주차 머신러닝 기초",
                max_follow_ups=0,
                difficulty=ExamDifficulty.MEDIUM,
                source_material_ids=[],
                bloom_counts=[
                    ExamQuestionBloomCountCommand(
                        bloom_level=BloomLevel.APPLY,
                        count=1,
                    )
                ],
            ),
        )
