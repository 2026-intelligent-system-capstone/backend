from collections.abc import Sequence
from datetime import UTC, datetime, timedelta
from uuid import UUID

import pytest

from app.async_job.domain.entity import (
    AsyncJob,
    AsyncJobTargetType,
    AsyncJobType,
)
from app.auth.application.exception import AuthForbiddenException
from app.auth.domain.entity import CurrentUser
from app.classroom.domain.entity import (
    Classroom,
    ClassroomMaterialIngestStatus,
)
from app.classroom.domain.usecase import ClassroomUseCase
from app.exam.application.exception import (
    ExamNotFoundException,
    ExamQuestionGenerationAlreadyInProgressException,
    ExamQuestionGenerationMaterialIngestFailedException,
    ExamQuestionGenerationMaterialNotFoundException,
    ExamQuestionGenerationMaterialNotReadyException,
    ExamQuestionGenerationUnavailableException,
    ExamQuestionInvalidPayloadException,
    ExamQuestionNotFoundException,
    ExamSessionUnavailableException,
)
from app.exam.application.service import ExamService
from app.exam.domain.command import (
    CreateExamCommand,
    CreateExamQuestionCommand,
    ExamCriterionCommand,
    ExamQuestionBloomCountCommand,
    ExamQuestionTypeCountCommand,
    GenerateExamQuestionsCommand,
    UpdateExamQuestionCommand,
)
from app.exam.domain.entity import (
    BloomLevel,
    Exam,
    ExamCriterion,
    ExamDifficulty,
    ExamGenerationStatus,
    ExamQuestionStatus,
    ExamQuestionType,
    ExamResult,
    ExamResultStatus,
    ExamSession,
    ExamSessionStatus,
    ExamStatus,
    ExamTurn,
    ExamType,
    RealtimeClientSecret,
)
from app.exam.domain.exception import ExamInvalidMaxAttemptsDomainException
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
NOW = datetime.now(UTC)
STARTS_AT = NOW - timedelta(hours=1)
ENDS_AT = NOW + timedelta(hours=1)
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
        _ = current_user
        return [self.classroom]

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
    max_attempts: int = 1,
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
        max_attempts=max_attempts,
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
        max_score=1.0,
        question_type=ExamQuestionType.SUBJECTIVE,
        bloom_level=BloomLevel.APPLY,
        difficulty=ExamDifficulty.MEDIUM,
        question_text="회귀와 분류의 차이를 설명하세요.",
        intent_text=(
            "1주차 머신러닝 기초 범위에서 지도학습의 핵심 구분을 "
            "설명하도록 유도"
        ),
        rubric_text=(
            "출력 형태와 학습 목표 차이를 포함하고, 핵심 개념과 예시를 "
            "함께 설명하면 정답"
        ),
        correct_answer_text="회귀와 분류",
        source_material_ids=[UUID("99999999-9999-9999-9999-999999999999")],
    )


def make_multiple_choice_question_command() -> CreateExamQuestionCommand:
    return CreateExamQuestionCommand(
        question_number=1,
        max_score=1.0,
        question_type=ExamQuestionType.MULTIPLE_CHOICE,
        bloom_level=BloomLevel.APPLY,
        difficulty=ExamDifficulty.MEDIUM,
        question_text="지도학습 예시를 고르세요.",
        intent_text="객관식에서 개념 분류 능력을 평가합니다.",
        rubric_text="정확한 개념 선택 여부를 평가합니다.",
        answer_options=["회귀", "분류", "강화학습"],
        correct_answer_text="회귀",
        source_material_ids=[],
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
    async_job_service: FakeAsyncJobService | None = None,
    question_generation_port: object | None = object(),
):
    session_repository = InMemoryExamSessionRepository()
    result_repository = InMemoryExamResultRepository()
    turn_repository = InMemoryExamTurnRepository()
    realtime_port = FakeRealtimeSessionPort()
    fake_async_job_service = async_job_service
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
        question_generation_port=question_generation_port,
        async_job_service=fake_async_job_service,
    )
    return (
        service,
        session_repository,
        result_repository,
        turn_repository,
        realtime_port,
        fake_async_job_service,
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
        max_attempts=1,
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


def test_exam_create_rejects_invalid_max_attempts():
    with pytest.raises(ExamInvalidMaxAttemptsDomainException):
        Exam.create(
            classroom_id=CLASSROOM_ID,
            title="중간 평가",
            description="1주차 범위 평가",
            exam_type=ExamType.MIDTERM,
            duration_minutes=60,
            starts_at=STARTS_AT,
            ends_at=ENDS_AT,
            max_attempts=0,
            week=WEEK,
            criteria=[],
        )


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
            max_attempts=1,
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
    assert exam.max_attempts == 1
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
            max_attempts=1,
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


def test_create_exam_question_command_requires_mc_options():
    with pytest.raises(ValueError, match="answer_options"):
        CreateExamQuestionCommand(
            question_number=1,
            max_score=1.0,
            question_type=ExamQuestionType.MULTIPLE_CHOICE,
            bloom_level=BloomLevel.APPLY,
            difficulty=ExamDifficulty.MEDIUM,
            question_text="지도학습 예시를 고르세요.",
            intent_text="객관식에서 개념 분류 능력을 평가합니다.",
            rubric_text="정확한 개념 선택 여부를 평가합니다.",
            answer_options=[],
            correct_answer_text="회귀",
            source_material_ids=[],
        )


def test_create_exam_question_command_requires_mc_answer():
    with pytest.raises(ValueError, match="correct_answer_text"):
        CreateExamQuestionCommand(
            question_number=1,
            max_score=1.0,
            question_type=ExamQuestionType.MULTIPLE_CHOICE,
            bloom_level=BloomLevel.APPLY,
            difficulty=ExamDifficulty.MEDIUM,
            question_text="지도학습 예시를 고르세요.",
            intent_text="객관식에서 개념 분류 능력을 평가합니다.",
            rubric_text="정확한 개념 선택 여부를 평가합니다.",
            answer_options=["회귀", "분류"],
            correct_answer_text=None,
            source_material_ids=[],
        )


def test_create_exam_question_command_requires_two_mc_options():
    with pytest.raises(ValueError, match="at least two"):
        CreateExamQuestionCommand(
            question_number=1,
            max_score=1.0,
            question_type=ExamQuestionType.MULTIPLE_CHOICE,
            bloom_level=BloomLevel.APPLY,
            difficulty=ExamDifficulty.MEDIUM,
            question_text="지도학습 예시를 고르세요.",
            intent_text="객관식에서 개념 분류 능력을 평가합니다.",
            rubric_text="정확한 개념 선택 여부를 평가합니다.",
            answer_options=["회귀"],
            correct_answer_text="회귀",
            source_material_ids=[],
        )


def test_create_exam_question_command_requires_correct_answer_for_subjective():
    with pytest.raises(ValueError, match="correct_answer_text"):
        CreateExamQuestionCommand(
            question_number=1,
            max_score=1.0,
            question_type=ExamQuestionType.SUBJECTIVE,
            bloom_level=BloomLevel.APPLY,
            difficulty=ExamDifficulty.MEDIUM,
            question_text="회귀와 분류의 차이를 설명하세요.",
            intent_text="주관식에서 핵심 개념 구분 능력을 평가합니다.",
            rubric_text="핵심 개념과 예시를 설명하면 정답",
            correct_answer_text=None,
            source_material_ids=[],
        )


def test_update_exam_question_command_requires_options_when_switching_to_mc():
    with pytest.raises(ValueError, match="answer_options"):
        UpdateExamQuestionCommand(
            question_type=ExamQuestionType.MULTIPLE_CHOICE,
            correct_answer_text="회귀",
        )


def test_update_exam_question_command_requires_answer_when_switching_to_mc():
    with pytest.raises(ValueError, match="correct_answer_text"):
        UpdateExamQuestionCommand(
            question_type=ExamQuestionType.MULTIPLE_CHOICE,
            answer_options=["회귀", "분류"],
        )


def test_update_exam_question_command_requires_rubric_when_switching_to_oral():
    with pytest.raises(ValueError, match="rubric_text"):
        UpdateExamQuestionCommand(question_type=ExamQuestionType.ORAL)


def test_update_exam_question_command_requires_answer_for_subjective():
    with pytest.raises(ValueError, match="correct_answer_text"):
        UpdateExamQuestionCommand(question_type=ExamQuestionType.SUBJECTIVE)


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
                max_attempts=1,
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
    assert exam.max_attempts == 1
    assert exam.criteria[0].excellent_definition == (
        "핵심 개념과 관계를 정확히 설명한다."
    )


@pytest.mark.asyncio
async def test_list_student_exams_marks_closed_exam_as_completed():
    closed_exam = make_exam()
    closed_exam.status = ExamStatus.CLOSED
    service, _, _, _, _, _ = build_service(exams=[closed_exam])

    exams = await service.list_student_exams(
        current_user=make_current_user(
            role=UserRole.STUDENT,
            user_id=STUDENT_ID,
        )
    )

    assert len(exams) == 1
    assert exams[0].exam.id == EXAM_ID
    assert exams[0].is_completed is True
    assert exams[0].can_enter is False
    assert exams[0].latest_result is None


@pytest.mark.asyncio
async def test_list_student_exams_marks_submitted_student_completed():
    exam = make_exam()
    session = ExamSession.start(
        exam_id=EXAM_ID,
        student_id=STUDENT_ID,
        started_at=STARTS_AT,
        attempt_number=1,
        expires_at=ENDS_AT,
    )
    session.complete(ENDS_AT)
    result = session.create_pending_result()
    result.finalize(
        overall_score=91.0,
        summary="핵심 개념과 적용 예시를 모두 설명했습니다.",
        submitted_at=ENDS_AT,
    )
    service, session_repository, result_repository, _, _, _ = build_service(
        exams=[exam]
    )
    await session_repository.save(session)
    await result_repository.save(result)

    exams = await service.list_student_exams(
        current_user=make_current_user(
            role=UserRole.STUDENT,
            user_id=STUDENT_ID,
        )
    )

    assert len(exams) == 1
    assert exams[0].exam.id == EXAM_ID
    assert exams[0].is_completed is True
    assert exams[0].can_enter is False
    assert exams[0].latest_result.id == result.id


@pytest.mark.asyncio
async def test_list_student_exams_returns_latest_completed_result():
    exam = make_exam(max_attempts=2)
    first_session = ExamSession.start(
        exam_id=EXAM_ID,
        student_id=STUDENT_ID,
        started_at=STARTS_AT,
        attempt_number=1,
        expires_at=ENDS_AT,
    )
    first_session.complete(STARTS_AT + timedelta(minutes=10))
    completed_result = first_session.create_pending_result()
    completed_result.finalize(
        overall_score=88.0,
        summary="첫 번째 응시 완료",
        submitted_at=STARTS_AT + timedelta(minutes=10),
    )
    second_session = ExamSession.start(
        exam_id=EXAM_ID,
        student_id=STUDENT_ID,
        started_at=STARTS_AT + timedelta(minutes=20),
        attempt_number=2,
        expires_at=ENDS_AT,
    )
    pending_result = second_session.create_pending_result()
    service, session_repository, result_repository, _, _, _ = build_service(
        exams=[exam]
    )
    await session_repository.save(first_session)
    await session_repository.save(second_session)
    await result_repository.save(completed_result)
    await result_repository.save(pending_result)

    exams = await service.list_student_exams(
        current_user=make_current_user(
            role=UserRole.STUDENT,
            user_id=STUDENT_ID,
        )
    )

    assert len(exams) == 1
    assert exams[0].is_completed is True
    assert exams[0].can_enter is False
    assert exams[0].latest_result.id == completed_result.id


@pytest.mark.asyncio
async def test_get_student_exam_returns_result_only_gate_for_completed_exam():
    closed_exam = make_exam()
    closed_exam.status = ExamStatus.CLOSED
    service, _, _, _, _, _ = build_service(exams=[closed_exam])

    student_exam = await service.get_student_exam(
        exam_id=EXAM_ID,
        current_user=make_current_user(
            role=UserRole.STUDENT,
            user_id=STUDENT_ID,
        ),
    )

    assert student_exam.exam.id == EXAM_ID
    assert student_exam.is_completed is True
    assert student_exam.can_enter is False


@pytest.mark.asyncio
async def test_list_student_exams_marks_upcoming_exam_as_not_enterable():
    upcoming_exam = make_exam()
    upcoming_exam.starts_at = datetime.now(UTC) + timedelta(hours=1)
    upcoming_exam.ends_at = datetime.now(UTC) + timedelta(hours=2)
    service, _, _, _, _, _ = build_service(exams=[upcoming_exam])

    exams = await service.list_student_exams(
        current_user=make_current_user(
            role=UserRole.STUDENT,
            user_id=STUDENT_ID,
        )
    )

    assert len(exams) == 1
    assert exams[0].is_completed is False
    assert exams[0].can_enter is False
    assert exams[0].latest_result is None


@pytest.mark.asyncio
async def test_get_student_exam_returns_latest_completed_result():
    exam = make_exam(max_attempts=2)
    first_session = ExamSession.start(
        exam_id=EXAM_ID,
        student_id=STUDENT_ID,
        started_at=STARTS_AT,
        attempt_number=1,
        expires_at=ENDS_AT,
    )
    first_session.complete(STARTS_AT + timedelta(minutes=10))
    completed_result = first_session.create_pending_result()
    completed_result.finalize(
        overall_score=88.0,
        summary="첫 번째 응시 완료",
        submitted_at=STARTS_AT + timedelta(minutes=10),
    )
    second_session = ExamSession.start(
        exam_id=EXAM_ID,
        student_id=STUDENT_ID,
        started_at=STARTS_AT + timedelta(minutes=20),
        attempt_number=2,
        expires_at=ENDS_AT,
    )
    pending_result = second_session.create_pending_result()
    service, session_repository, result_repository, _, _, _ = build_service(
        exams=[exam]
    )
    await session_repository.save(first_session)
    await session_repository.save(second_session)
    await result_repository.save(completed_result)
    await result_repository.save(pending_result)

    student_exam = await service.get_student_exam(
        exam_id=EXAM_ID,
        current_user=make_current_user(
            role=UserRole.STUDENT,
            user_id=STUDENT_ID,
        ),
    )

    assert student_exam.is_completed is True
    assert student_exam.can_enter is False
    assert student_exam.latest_result.id == completed_result.id


@pytest.mark.asyncio
async def test_get_student_exam_marks_upcoming_exam_as_not_enterable():
    upcoming_exam = make_exam()
    upcoming_exam.starts_at = datetime.now(UTC) + timedelta(hours=1)
    upcoming_exam.ends_at = datetime.now(UTC) + timedelta(hours=2)
    service, _, _, _, _, _ = build_service(exams=[upcoming_exam])

    student_exam = await service.get_student_exam(
        exam_id=EXAM_ID,
        current_user=make_current_user(
            role=UserRole.STUDENT,
            user_id=STUDENT_ID,
        ),
    )

    assert student_exam.is_completed is False
    assert student_exam.can_enter is False
    assert student_exam.latest_result is None


@pytest.mark.asyncio
async def test_get_student_exam_raises_for_other_classroom():
    service, _, _, _, _, _ = build_service(
        exams=[
            make_exam(classroom_id=UUID("77777777-7777-7777-7777-777777777777"))
        ]
    )

    with pytest.raises(ExamNotFoundException):
        await service.get_student_exam(
            exam_id=EXAM_ID,
            current_user=make_current_user(
                role=UserRole.STUDENT,
                user_id=STUDENT_ID,
            ),
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
    assert question.max_score == 1.0
    assert question.question_type is ExamQuestionType.SUBJECTIVE
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
            intent_text="수정된 범위와 평가 의도",
            max_score=2.5,
        ),
    )

    assert question.question_text == "수정된 질문"
    assert question.intent_text == "수정된 범위와 평가 의도"
    assert question.max_score == 2.5
    assert question.question_type is ExamQuestionType.SUBJECTIVE
    assert question.status is ExamQuestionStatus.REVIEWED


@pytest.mark.asyncio
async def test_update_exam_question_rejects_mc_without_required_answer_fields():
    exam = make_exam()
    created = exam.add_question(
        **make_multiple_choice_question_command().model_dump()
    )
    service, _, _, _, _, _ = build_service(exams=[exam])

    with pytest.raises(ExamQuestionInvalidPayloadException):
        await service.update_exam_question(
            classroom_id=CLASSROOM_ID,
            exam_id=EXAM_ID,
            question_id=created.id,
            current_user=make_current_user(
                role=UserRole.PROFESSOR,
                user_id=PROFESSOR_ID,
            ),
            command=UpdateExamQuestionCommand(answer_options=[]),
        )


@pytest.mark.asyncio
async def test_update_legacy_multiple_choice_question_allows_text_only_edit():
    exam = make_exam()
    created = exam.add_question(
        question_number=1,
        max_score=1.0,
        question_type=ExamQuestionType.MULTIPLE_CHOICE,
        bloom_level=BloomLevel.APPLY,
        difficulty=ExamDifficulty.MEDIUM,
        question_text="기존 객관식 문항",
        intent_text="기존 의도",
        rubric_text="기존 루브릭",
        answer_options=[],
        correct_answer_text="회귀",
        source_material_ids=[],
    )
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
            question_text="수정된 기존 객관식 문항"
        ),
    )

    assert question.question_text == "수정된 기존 객관식 문항"
    assert question.question_type is ExamQuestionType.MULTIPLE_CHOICE
    assert question.answer_options == []
    assert question.correct_answer_text == "회귀"


@pytest.mark.asyncio
async def test_update_legacy_mc_rejects_answer_edit_without_full_contract():
    exam = make_exam()
    created = exam.add_question(
        question_number=1,
        max_score=1.0,
        question_type=ExamQuestionType.MULTIPLE_CHOICE,
        bloom_level=BloomLevel.APPLY,
        difficulty=ExamDifficulty.MEDIUM,
        question_text="기존 객관식 문항",
        intent_text="기존 의도",
        rubric_text="기존 루브릭",
        answer_options=[],
        correct_answer_text="회귀",
        source_material_ids=[],
    )
    service, _, _, _, _, _ = build_service(exams=[exam])

    with pytest.raises(ExamQuestionInvalidPayloadException):
        await service.update_exam_question(
            classroom_id=CLASSROOM_ID,
            exam_id=EXAM_ID,
            question_id=created.id,
            current_user=make_current_user(
                role=UserRole.PROFESSOR,
                user_id=PROFESSOR_ID,
            ),
            command=UpdateExamQuestionCommand(correct_answer_text="분류"),
        )


@pytest.mark.asyncio
async def test_update_mc_question_to_subjective_keeps_exact_answer():
    exam = make_exam()
    created = exam.add_question(
        **make_multiple_choice_question_command().model_dump()
    )
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
            question_type=ExamQuestionType.SUBJECTIVE,
            question_text="회귀의 정의를 한 문장으로 설명하세요.",
            correct_answer_text="입력과 출력의 관계를 예측하는 지도학습 방식",
        ),
    )

    assert question.question_type is ExamQuestionType.SUBJECTIVE
    assert question.answer_options == []
    assert (
        question.correct_answer_text
        == "입력과 출력의 관계를 예측하는 지도학습 방식"
    )


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
async def test_start_exam_session_raises_unavailable_for_closed_exam():
    closed_exam = make_exam()
    closed_exam.status = ExamStatus.CLOSED
    service, _, _, _, _, _ = build_service(exams=[closed_exam])

    with pytest.raises(ExamSessionUnavailableException):
        await service.start_exam_session(
            exam_id=EXAM_ID,
            current_user=make_current_user(
                role=UserRole.STUDENT,
                user_id=STUDENT_ID,
            ),
        )


@pytest.mark.asyncio
async def test_start_exam_session_raises_unavailable_before_exam_window_opens():
    upcoming_exam = make_exam()
    upcoming_exam.starts_at = datetime.now(UTC) + timedelta(hours=1)
    upcoming_exam.ends_at = datetime.now(UTC) + timedelta(hours=2)
    service, _, _, _, _, _ = build_service(exams=[upcoming_exam])

    with pytest.raises(ExamSessionUnavailableException):
        await service.start_exam_session(
            exam_id=EXAM_ID,
            current_user=make_current_user(
                role=UserRole.STUDENT,
                user_id=STUDENT_ID,
            ),
        )


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
async def test_generate_exam_questions_enqueues_job_and_marks_exam_queued():
    material_id = UUID("99999999-9999-9999-9999-999999999999")
    async_job_service = FakeAsyncJobService()
    service, _, _, _, _, _ = build_service(
        exams=[make_exam()],
        materials=[make_material_result(material_id=material_id)],
        async_job_service=async_job_service,
    )

    result = await service.generate_exam_questions(
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
            question_type_counts=[
                ExamQuestionTypeCountCommand(
                    question_type=ExamQuestionType.ORAL,
                    count=1,
                )
            ],
        ),
    )

    assert result.exam_id == EXAM_ID
    assert result.generation_status is ExamGenerationStatus.QUEUED
    assert result.generation_requested_at is not None
    assert result.generation_error is None
    assert result.job.job_type is AsyncJobType.EXAM_QUESTION_GENERATION
    assert result.job.status.value == "queued"
    assert len(async_job_service.enqueue_calls) == 1
    enqueue_call = async_job_service.enqueue_calls[0]
    assert enqueue_call["job_type"] is AsyncJobType.EXAM_QUESTION_GENERATION
    assert enqueue_call["target_type"] is AsyncJobTargetType.EXAM
    assert enqueue_call["target_id"] == EXAM_ID
    assert enqueue_call["requested_by"] == PROFESSOR_ID
    assert enqueue_call["dedupe_key"] == f"exam-question-generation:{EXAM_ID}"
    payload = enqueue_call["payload"]
    assert payload["exam_id"] == str(EXAM_ID)
    assert payload["classroom_id"] == str(CLASSROOM_ID)
    assert payload["request"]["scope_text"] == "1주차 머신러닝 기초"
    assert payload["request"]["max_follow_ups"] == 2
    assert payload["request"]["difficulty"] == "medium"
    assert payload["request"]["source_material_ids"] == [str(material_id)]
    assert payload["request"]["bloom_counts"] == [
        {"bloom_level": "apply", "count": 1}
    ]
    assert payload["request"]["question_type_counts"] == [
        {"question_type": "oral", "count": 1}
    ]
    assert "question_type_strategy" not in payload["request"]
    assert "total_question_count" not in payload["request"]
    saved_exam = service.repository.exams[EXAM_ID]
    assert saved_exam.generation_status is ExamGenerationStatus.QUEUED
    assert saved_exam.generation_job_id == result.job.job_id
    assert saved_exam.generation_requested_at is not None
    assert result.generation_requested_at == saved_exam.generation_requested_at
    assert saved_exam.generation_completed_at is None


@pytest.mark.asyncio
async def test_generate_exam_questions_normalizes_strategy_counts():
    material_id = UUID("99999999-9999-9999-9999-999999999999")
    async_job_service = FakeAsyncJobService()
    service, _, _, _, _, _ = build_service(
        exams=[make_exam()],
        materials=[make_material_result(material_id=material_id)],
        async_job_service=async_job_service,
    )

    result = await service.generate_exam_questions(
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
            total_question_count=4,
            question_type_strategy="oral_focus",
            bloom_counts=[
                ExamQuestionBloomCountCommand(
                    bloom_level=BloomLevel.REMEMBER,
                    count=1,
                ),
                ExamQuestionBloomCountCommand(
                    bloom_level=BloomLevel.APPLY,
                    count=3,
                ),
            ],
        ),
    )

    payload = async_job_service.enqueue_calls[0]["payload"]
    question_type_counts = payload["request"]["question_type_counts"]
    assert result.generation_status is ExamGenerationStatus.QUEUED
    assert sum(item["count"] for item in question_type_counts) == 4
    assert {item["question_type"] for item in question_type_counts} == {
        "multiple_choice",
        "subjective",
        "oral",
    }
    counts_by_type = {
        item["question_type"]: item["count"] for item in question_type_counts
    }
    assert question_type_counts[0]["question_type"] == "oral"
    assert counts_by_type["oral"] >= counts_by_type["subjective"]
    assert counts_by_type["oral"] >= counts_by_type["multiple_choice"]
    assert "question_type_strategy" not in payload["request"]
    assert "total_question_count" not in payload["request"]


@pytest.mark.asyncio
async def test_generate_exam_questions_already_in_progress_raises():
    material_id = UUID("99999999-9999-9999-9999-999999999999")
    exam = make_exam()
    exam.mark_generation_queued(
        job_id=UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"),
        requested_at=STARTS_AT,
    )
    async_job_service = FakeAsyncJobService()
    service, _, _, _, _, _ = build_service(
        exams=[exam],
        materials=[make_material_result(material_id=material_id)],
        async_job_service=async_job_service,
    )

    with pytest.raises(ExamQuestionGenerationAlreadyInProgressException):
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
                        bloom_level=BloomLevel.ANALYZE,
                        count=1,
                    )
                ],
                question_type_counts=[
                    ExamQuestionTypeCountCommand(
                        question_type=ExamQuestionType.MULTIPLE_CHOICE,
                        count=1,
                    )
                ],
            ),
        )

    assert async_job_service.enqueue_calls == []


@pytest.mark.asyncio
async def test_generate_exam_questions_invalid_material_raises():
    async_job_service = FakeAsyncJobService()
    service, _, _, _, _, _ = build_service(
        exams=[make_exam()],
        materials=[],
        async_job_service=async_job_service,
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
                question_type_counts=[
                    ExamQuestionTypeCountCommand(
                        question_type=ExamQuestionType.SUBJECTIVE,
                        count=1,
                    )
                ],
            ),
        )

    assert async_job_service.enqueue_calls == []


@pytest.mark.asyncio
async def test_generate_exam_questions_pending_material_raises():
    material_id = UUID("99999999-9999-9999-9999-999999999999")
    async_job_service = FakeAsyncJobService()
    service, _, _, _, _, _ = build_service(
        exams=[make_exam()],
        materials=[
            make_material_result(
                material_id=material_id,
                ingest_status=ClassroomMaterialIngestStatus.PENDING,
            )
        ],
        async_job_service=async_job_service,
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
                question_type_counts=[
                    ExamQuestionTypeCountCommand(
                        question_type=ExamQuestionType.SUBJECTIVE,
                        count=1,
                    )
                ],
            ),
        )

    assert async_job_service.enqueue_calls == []


@pytest.mark.asyncio
async def test_generate_exam_questions_failed_material_raises_before_enqueue():
    material_id = UUID("99999999-9999-9999-9999-999999999999")
    async_job_service = FakeAsyncJobService()
    service, _, _, _, _, _ = build_service(
        exams=[make_exam()],
        materials=[
            make_material_result(
                material_id=material_id,
                ingest_status=ClassroomMaterialIngestStatus.FAILED,
            )
        ],
        async_job_service=async_job_service,
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
                question_type_counts=[
                    ExamQuestionTypeCountCommand(
                        question_type=ExamQuestionType.SUBJECTIVE,
                        count=1,
                    )
                ],
            ),
        )

    assert async_job_service.enqueue_calls == []


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
                question_type_counts=[
                    ExamQuestionTypeCountCommand(
                        question_type=ExamQuestionType.SUBJECTIVE,
                        count=1,
                    )
                ],
            ),
        )
