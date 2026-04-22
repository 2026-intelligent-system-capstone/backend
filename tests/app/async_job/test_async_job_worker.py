import asyncio
from datetime import UTC, datetime
from io import BytesIO
from uuid import UUID

import pytest

from app.async_job.application.service.worker import AsyncJobWorker
from app.async_job.domain.entity import (
    AsyncJob,
    AsyncJobStatus,
    AsyncJobTargetType,
    AsyncJobType,
)
from app.async_job.domain.repository import AsyncJobRepository
from app.classroom.domain.entity import (
    Classroom,
    ClassroomMaterial,
    ClassroomMaterialIngestCapability,
    ClassroomMaterialIngestStatus,
    ClassroomMaterialOriginalFile,
    ClassroomMaterialScopeCandidate,
    ClassroomMaterialSourceKind,
)
from app.classroom.domain.exception import (
    ClassroomMaterialIngestDomainException,
)
from app.classroom.domain.repository.classroom import ClassroomRepository
from app.classroom.domain.repository.classroom_material import (
    ClassroomMaterialRepository,
)
from app.classroom.domain.service import (
    ClassroomMaterialIngestPort,
    ClassroomMaterialIngestResult,
)
from app.exam.application.exception import ExamQuestionGenerationFailedException
from app.exam.domain.entity import (
    BloomLevel,
    Exam,
    ExamCriterion,
    ExamDifficulty,
    ExamGenerationStatus,
    ExamQuestionType,
    ExamResult,
    ExamResultStatus,
    ExamSession,
    ExamSessionStatus,
    ExamTurn,
    ExamTurnEventType,
    ExamTurnRole,
    ExamType,
)
from app.exam.domain.repository.exam import (
    ExamRepository,
    ExamResultRepository,
    ExamSessionRepository,
    ExamTurnRepository,
)
from app.exam.domain.service import (
    ExamQuestionGenerationPort,
    GeneratedExamQuestionDraft,
)
from app.exam.domain.service.evaluator import (
    EvaluateExamResult,
    ExamResultEvaluationCriterionScore,
    ExamResultEvaluationPort,
)
from app.file.domain.entity.file import File, FileStatus
from app.file.domain.entity.file_download import FileDownload
from app.file.domain.usecase.file import FileUseCase
from core.common.exceptions.base import CustomException

ORG_ID = UUID("11111111-1111-1111-1111-111111111111")
CLASSROOM_ID = UUID("22222222-2222-2222-2222-222222222222")
MATERIAL_ID = UUID("33333333-3333-3333-3333-333333333333")
FILE_ID = UUID("44444444-4444-4444-4444-444444444444")
JOB_REQUESTED_BY = UUID("55555555-5555-5555-5555-555555555555")
EXAM_ID = UUID("66666666-6666-6666-6666-666666666666")
SESSION_ID = UUID("77777777-7777-7777-7777-777777777777")
STUDENT_ID = UUID("88888888-8888-8888-8888-888888888888")
RESULT_ID = UUID("99999999-9999-9999-9999-999999999999")
TURN_ID = UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
CRITERION_ID = UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")


class InMemoryAsyncJobRepository(AsyncJobRepository):
    def __init__(self, jobs: list[AsyncJob] | None = None):
        self.jobs = {job.id: job for job in jobs or []}
        self.saved_job_ids: list[UUID] = []
        self._dedupe_locks: dict[str, asyncio.Lock] = {}

    async def save(self, entity: AsyncJob) -> None:
        self.jobs[entity.id] = entity
        self.saved_job_ids.append(entity.id)

    from contextlib import asynccontextmanager

    @asynccontextmanager
    async def dedupe_key_lock(self, *, dedupe_key: str):
        lock = self._dedupe_locks.setdefault(dedupe_key, asyncio.Lock())
        async with lock:
            yield

    async def get_by_id(self, entity_id: UUID) -> AsyncJob | None:
        return self.jobs.get(entity_id)

    async def list(self):
        return list(self.jobs.values())

    async def get_latest_by_target(self, *, target_id: UUID) -> AsyncJob | None:
        matches = [job for job in self.jobs.values() if job.target_id == target_id]
        matches.sort(key=lambda job: job.created_at, reverse=True)
        return matches[0] if matches else None

    async def get_active_by_dedupe_key(self, *, dedupe_key: str) -> AsyncJob | None:
        matches = [job for job in self.jobs.values() if job.dedupe_key == dedupe_key and job.status in {AsyncJobStatus.QUEUED, AsyncJobStatus.RUNNING}]
        matches.sort(key=lambda job: job.available_at, reverse=True)
        return matches[0] if matches else None

    async def claim_next_runnable(self, *, now: datetime) -> AsyncJob | None:
        queued_jobs = [job for job in self.jobs.values() if job.status is AsyncJobStatus.QUEUED and job.available_at <= now]
        queued_jobs.sort(key=lambda job: job.available_at)
        return queued_jobs[0] if queued_jobs else None

    async def list_by_target(self, *, target_id: UUID):
        return [job for job in self.jobs.values() if job.target_id == target_id]


class InMemoryClassroomRepository(ClassroomRepository):
    def __init__(self, classrooms: list[Classroom] | None = None):
        self.classrooms = {classroom.id: classroom for classroom in classrooms or []}

    async def save(self, entity: Classroom) -> None:
        self.classrooms[entity.id] = entity

    async def get_by_id(self, entity_id: UUID) -> Classroom | None:
        return self.classrooms.get(entity_id)

    async def list(self):
        return list(self.classrooms.values())

    async def get_by_organization_and_name_and_term(
        self,
        organization_id: UUID,
        name: str,
        grade: int,
        semester: str,
        section: str,
    ):
        _ = (organization_id, name, grade, semester, section)
        return None

    async def list_by_organization(self, organization_id: UUID):
        return [classroom for classroom in self.classrooms.values() if classroom.organization_id == organization_id]

    async def delete(self, entity: Classroom) -> None:
        self.classrooms.pop(entity.id, None)


class InMemoryClassroomMaterialRepository(ClassroomMaterialRepository):
    def __init__(self, materials: list[ClassroomMaterial] | None = None):
        self.materials = {material.id: material for material in materials or []}

    async def save(self, entity: ClassroomMaterial) -> None:
        self.materials[entity.id] = entity

    async def get_by_id(self, entity_id: UUID) -> ClassroomMaterial | None:
        return self.materials.get(entity_id)

    async def list(self):
        return list(self.materials.values())

    async def list_by_classroom(self, classroom_id: UUID):
        return [material for material in self.materials.values() if material.classroom_id == classroom_id]

    async def delete(self, entity: ClassroomMaterial) -> None:
        self.materials.pop(entity.id, None)


class FakeFileUseCase(FileUseCase):
    def __init__(self, *, files: dict[UUID, File] | None = None):
        self.files = files or {}
        self.downloaded_file_ids: list[UUID] = []
        self.events: list[str] = []

    async def create_file(self, command):
        raise NotImplementedError

    async def upload_file(
        self,
        *,
        file_upload,
        directory: str,
        status: FileStatus = FileStatus.PENDING,
    ):
        raise NotImplementedError

    async def get_file(self, file_id: UUID) -> File:
        self.events.append(f"get_file:{file_id}")
        return self.files[file_id]

    async def get_file_download(self, file_id: UUID) -> FileDownload:
        self.events.append(f"get_file_download:{file_id}")
        self.downloaded_file_ids.append(file_id)
        return FileDownload(file=self.files[file_id], content=BytesIO(b"pdf-content"))

    async def list_files(self):
        return list(self.files.values())

    async def update_file(self, file_id: UUID, command):
        raise NotImplementedError

    async def delete_file(self, file_id: UUID):
        raise NotImplementedError


class FakeMaterialIngestPort(ClassroomMaterialIngestPort):
    def __init__(
        self,
        *,
        result: ClassroomMaterialIngestResult | None = None,
        error: Exception | None = None,
        events: list[str] | None = None,
    ):
        self.result = result or ClassroomMaterialIngestResult()
        self.error = error
        self.requests = []
        self.events = events

    async def ingest_material(self, *, request):
        if self.events is not None:
            self.events.append("ingest_material")
        self.requests.append(request)
        if self.error is not None:
            raise self.error
        return self.result


class InMemoryExamRepository(ExamRepository):
    def __init__(self, exams: list[Exam] | None = None):
        self.exams = {exam.id: exam for exam in exams or []}
        self.events: list[str] = []

    async def save(self, entity: Exam) -> None:
        self.events.append(f"save_exam:{entity.generation_status.value if entity.generation_status else 'none'}")
        self.exams[entity.id] = entity

    async def get_by_id(self, entity_id: UUID) -> Exam | None:
        self.events.append(f"get_exam:{entity_id}")
        return self.exams.get(entity_id)

    async def list(self):
        return list(self.exams.values())

    async def list_by_classroom(self, classroom_id: UUID):
        return [exam for exam in self.exams.values() if exam.classroom_id == classroom_id]


class FakeExamQuestionGenerationPort(ExamQuestionGenerationPort):
    def __init__(
        self,
        *,
        drafts: list[GeneratedExamQuestionDraft] | None = None,
        error: Exception | None = None,
        events: list[str] | None = None,
    ):
        self.drafts = drafts or []
        self.error = error
        self.requests = []
        self.events = events

    async def generate_questions(self, *, request):
        if self.events is not None:
            self.events.append("generate_questions")
        self.requests.append(request)
        if self.error is not None:
            raise self.error
        return self.drafts


class InMemoryExamSessionRepository(ExamSessionRepository):
    def __init__(self, sessions: list[ExamSession] | None = None):
        self.sessions = {session.id: session for session in sessions or []}

    async def save(self, entity: ExamSession) -> None:
        self.sessions[entity.id] = entity

    async def get_by_id(self, entity_id: UUID) -> ExamSession | None:
        return self.sessions.get(entity_id)

    async def list(self):
        return list(self.sessions.values())

    async def list_by_exam_and_student(
        self,
        *,
        exam_id: UUID,
        student_id: UUID,
    ):
        return [session for session in self.sessions.values() if session.exam_id == exam_id and session.student_id == student_id]

    async def list_by_exam_and_student_for_update(
        self,
        *,
        exam_id: UUID,
        student_id: UUID,
    ):
        return await self.list_by_exam_and_student(
            exam_id=exam_id,
            student_id=student_id,
        )


class InMemoryExamResultRepository(ExamResultRepository):
    def __init__(self, results: list[ExamResult] | None = None):
        self.results = {result.id: result for result in results or []}

    async def save(self, entity: ExamResult) -> None:
        self.results[entity.id] = entity

    async def get_by_id(self, entity_id: UUID) -> ExamResult | None:
        return self.results.get(entity_id)

    async def list(self):
        return list(self.results.values())

    async def list_by_exam_and_student(
        self,
        *,
        exam_id: UUID,
        student_id: UUID,
    ):
        return [result for result in self.results.values() if result.exam_id == exam_id and result.student_id == student_id]

    async def list_by_exam_and_student_for_update(
        self,
        *,
        exam_id: UUID,
        student_id: UUID,
    ):
        return await self.list_by_exam_and_student(
            exam_id=exam_id,
            student_id=student_id,
        )


class CompletedResultAppearsDuringResultLockRepository(InMemoryExamResultRepository):
    def __init__(self, results: list[ExamResult] | None = None):
        super().__init__(results)
        self.completed_result_injected = False

    async def list_by_exam_and_student_for_update(
        self,
        *,
        exam_id: UUID,
        student_id: UUID,
    ):
        if not self.completed_result_injected:
            current_result = self.results[RESULT_ID]
            current_result.status = ExamResultStatus.COMPLETED
            current_result.submitted_at = datetime(2026, 4, 1, 10, 0, tzinfo=UTC)
            self.completed_result_injected = True
        return await super().list_by_exam_and_student_for_update(
            exam_id=exam_id,
            student_id=student_id,
        )


class CompletedResultAppearsAfterEvaluationRepository(InMemoryExamResultRepository):
    def __init__(self, results: list[ExamResult] | None = None):
        super().__init__(results)
        self.lock_call_count = 0
        self.completed_result_injected = False
        self.seen_student_ids: list[UUID] = []

    async def list_by_exam_and_student_for_update(
        self,
        *,
        exam_id: UUID,
        student_id: UUID,
    ):
        self.lock_call_count += 1
        self.seen_student_ids.append(student_id)
        if self.lock_call_count == 2 and not self.completed_result_injected:
            current_result = self.results[RESULT_ID]
            current_result.status = ExamResultStatus.COMPLETED
            current_result.submitted_at = datetime(2026, 4, 1, 10, 5, tzinfo=UTC)
            self.completed_result_injected = True
        return await super().list_by_exam_and_student_for_update(
            exam_id=exam_id,
            student_id=student_id,
        )


class InMemoryExamTurnRepository(ExamTurnRepository):
    def __init__(self, turns: list[ExamTurn] | None = None):
        self.turns = {turn.id: turn for turn in turns or []}

    async def save(self, entity: ExamTurn) -> None:
        self.turns[entity.id] = entity

    async def get_by_id(self, entity_id: UUID) -> ExamTurn | None:
        return self.turns.get(entity_id)

    async def list(self):
        return list(self.turns.values())

    async def list_by_session(self, *, session_id: UUID):
        return [turn for turn in sorted(self.turns.values(), key=lambda item: item.sequence) if turn.session_id == session_id]


class FakeExamResultEvaluationPort(ExamResultEvaluationPort):
    def __init__(
        self,
        *,
        result: EvaluateExamResult | None = None,
        error: Exception | None = None,
        events: list[str] | None = None,
    ):
        self.result = result or EvaluateExamResult(summary="평가 요약")
        self.error = error
        self.requests = []
        self.events = events

    async def evaluate_result(self, *, request):
        if self.events is not None:
            self.events.append("evaluate_result")
        self.requests.append(request)
        if self.error is not None:
            raise self.error
        return self.result


def make_classroom() -> Classroom:
    classroom = Classroom(
        organization_id=ORG_ID,
        name="AI 기초",
        professor_ids=[JOB_REQUESTED_BY],
        grade=3,
        semester="1학기",
        section="01",
        description="설명",
        student_ids=[],
        allow_student_material_access=True,
    )
    classroom.id = CLASSROOM_ID
    return classroom


def make_file() -> File:
    file = File(
        file_name="week1.pdf",
        file_path="classrooms/week1.pdf",
        file_extension="pdf",
        file_size=10,
        mime_type="application/pdf",
        status=FileStatus.ACTIVE,
    )
    file.id = FILE_ID
    return file


def make_material() -> ClassroomMaterial:
    material = ClassroomMaterial.create_file(
        classroom_id=CLASSROOM_ID,
        file_id=FILE_ID,
        title="1주차 자료",
        week=1,
        description="소개 자료",
        uploaded_by=JOB_REQUESTED_BY,
        original_file=ClassroomMaterialOriginalFile(
            file_name="week1.pdf",
            file_path="classrooms/week1.pdf",
            file_extension="pdf",
            file_size=10,
            mime_type="application/pdf",
        ),
        ingest_capability=ClassroomMaterialIngestCapability(supported=True),
        ingest_metadata={"mime_type": "application/pdf"},
    )
    material.id = MATERIAL_ID
    return material


def make_link_material(*, source_url: str) -> ClassroomMaterial:
    material = ClassroomMaterial.create_link(
        classroom_id=CLASSROOM_ID,
        source_url=source_url,
        title="링크 자료",
        week=1,
        description="외부 링크 자료",
        uploaded_by=JOB_REQUESTED_BY,
        ingest_capability=ClassroomMaterialIngestCapability(supported=True),
        ingest_metadata={"mime_type": "text/plain"},
    )
    material.id = MATERIAL_ID
    return material


def make_completed_material() -> ClassroomMaterial:
    material = make_material()
    material.mark_ingest_completed([
        ClassroomMaterialScopeCandidate(
            label="기초 개념",
            scope_text="머신러닝 개요",
            keywords=["머신러닝"],
            week_range="1주차",
            confidence=0.9,
        )
    ])
    return material


def make_exam() -> Exam:
    exam = Exam(
        classroom_id=CLASSROOM_ID,
        title="중간 평가",
        description="1주차 범위 평가",
        exam_type=ExamType.MIDTERM,
        duration_minutes=60,
        starts_at=datetime(2026, 4, 1, 9, 0, tzinfo=UTC),
        ends_at=datetime(2026, 4, 1, 10, 0, tzinfo=UTC),
        max_attempts=1,
        week=1,
        criteria=[
            ExamCriterion(
                exam_id=EXAM_ID,
                title="개념 이해",
                description="핵심 개념 평가",
                weight=100,
                sort_order=1,
                excellent_definition="정확",
                average_definition="보통",
                poor_definition="부족",
            )
        ],
    )
    exam.id = EXAM_ID
    return exam


def make_material_ingest_job() -> AsyncJob:
    job = AsyncJob.enqueue(
        job_type=AsyncJobType.MATERIAL_INGEST,
        target_type=AsyncJobTargetType.CLASSROOM_MATERIAL,
        target_id=MATERIAL_ID,
        requested_by=JOB_REQUESTED_BY,
        payload={
            "classroom_id": str(CLASSROOM_ID),
            "material_id": str(MATERIAL_ID),
            "file_id": str(FILE_ID),
        },
    )
    return job


def make_exam_generation_job() -> AsyncJob:
    job = AsyncJob.enqueue(
        job_type=AsyncJobType.EXAM_QUESTION_GENERATION,
        target_type=AsyncJobTargetType.EXAM,
        target_id=EXAM_ID,
        requested_by=JOB_REQUESTED_BY,
        payload={
            "exam_id": str(EXAM_ID),
            "classroom_id": str(CLASSROOM_ID),
            "request": {
                "scope_text": "1주차 머신러닝 기초",
                "max_follow_ups": 2,
                "difficulty": "medium",
                "source_material_ids": [str(MATERIAL_ID)],
                "bloom_counts": [{"bloom_level": "apply", "count": 1}],
                "question_type_counts": [{"question_type": "oral", "count": 1}],
            },
        },
        dedupe_key=f"exam-question-generation:{EXAM_ID}",
    )
    return job


def make_completed_session() -> ExamSession:
    session = ExamSession(
        exam_id=EXAM_ID,
        student_id=STUDENT_ID,
        status=ExamSessionStatus.COMPLETED,
        started_at=datetime(2026, 4, 1, 9, 0, tzinfo=UTC),
        last_activity_at=datetime(2026, 4, 1, 10, 0, tzinfo=UTC),
        ended_at=datetime(2026, 4, 1, 10, 0, tzinfo=UTC),
        attempt_number=1,
    )
    session.id = SESSION_ID
    return session


def make_pending_result() -> ExamResult:
    result = ExamResult(
        exam_id=EXAM_ID,
        session_id=SESSION_ID,
        student_id=STUDENT_ID,
        status=ExamResultStatus.PENDING,
    )
    result.id = RESULT_ID
    return result


def make_turn(
    *,
    content: str = "지도학습은 정답 레이블이 있는 데이터를 사용합니다.",
    metadata: dict[str, str] | None = None,
) -> ExamTurn:
    turn = ExamTurn.create(
        session_id=SESSION_ID,
        sequence=1,
        role=ExamTurnRole.STUDENT,
        event_type=ExamTurnEventType.ANSWER,
        content=content,
        created_at=datetime(2026, 4, 1, 9, 30, tzinfo=UTC),
        metadata=metadata or {},
    )
    turn.id = TURN_ID
    return turn


def make_exam_for_evaluation() -> Exam:
    exam = make_exam()
    exam.add_question(
        question_number=1,
        max_score=1.0,
        question_type=ExamQuestionType.ORAL,
        bloom_level=BloomLevel.APPLY,
        difficulty=ExamDifficulty.MEDIUM,
        question_text="지도학습의 정의를 설명하세요.",
        intent_text="지도학습의 핵심 개념과 적용 맥락 이해를 확인한다.",
        rubric_text="레이블 데이터, 학습 목표, 대표 예시를 설명하면 우수하다.",
        source_material_ids=[MATERIAL_ID],
    )
    exam.criteria[0].id = CRITERION_ID
    return exam


def make_multiple_choice_exam_for_evaluation() -> Exam:
    exam = make_exam()
    exam.add_question(
        question_number=1,
        max_score=5.0,
        question_type=ExamQuestionType.MULTIPLE_CHOICE,
        bloom_level=BloomLevel.UNDERSTAND,
        difficulty=ExamDifficulty.MEDIUM,
        question_text="지도학습에 해당하는 설명을 고르세요.",
        intent_text="지도학습의 정의를 정확히 구분하는지 평가한다.",
        rubric_text="정답 보기와 정확히 일치하는 답을 선택하면 만점이다.",
        answer_options=[
            "정답 레이블이 있는 데이터로 학습한다.",
            "보상으로 학습한다.",
        ],
        correct_answer_text="정답 레이블이 있는 데이터로 학습한다.",
        source_material_ids=[MATERIAL_ID],
    )
    exam.criteria[0].id = CRITERION_ID
    return exam


def make_subjective_exam_for_evaluation() -> Exam:
    exam = make_exam()
    exam.add_question(
        question_number=1,
        max_score=3.0,
        question_type=ExamQuestionType.SUBJECTIVE,
        bloom_level=BloomLevel.REMEMBER,
        difficulty=ExamDifficulty.EASY,
        question_text="지도학습에서 사용하는 데이터는 무엇인가요?",
        intent_text="핵심 용어를 정확히 기억하는지 평가한다.",
        rubric_text="정답과 exact match 되면 만점이다.",
        correct_answer_text="레이블 데이터",
        source_material_ids=[MATERIAL_ID],
    )
    exam.criteria[0].id = CRITERION_ID
    return exam


def make_mixed_exam_for_evaluation() -> Exam:
    exam = make_exam()
    exam.add_question(
        question_number=1,
        max_score=5.0,
        question_type=ExamQuestionType.MULTIPLE_CHOICE,
        bloom_level=BloomLevel.UNDERSTAND,
        difficulty=ExamDifficulty.MEDIUM,
        question_text="지도학습에 해당하는 설명을 고르세요.",
        intent_text="지도학습의 정의를 정확히 구분하는지 평가한다.",
        rubric_text="",
        answer_options=[
            "정답 레이블이 있는 데이터로 학습한다.",
            "보상으로 학습한다.",
        ],
        correct_answer_text="정답 레이블이 있는 데이터로 학습한다.",
        source_material_ids=[MATERIAL_ID],
    )
    exam.add_question(
        question_number=2,
        max_score=5.0,
        question_type=ExamQuestionType.ORAL,
        bloom_level=BloomLevel.APPLY,
        difficulty=ExamDifficulty.MEDIUM,
        question_text="지도학습의 장단점을 설명하세요.",
        intent_text="개념 이해와 적용 맥락 설명 능력을 평가한다.",
        rubric_text="장점과 한계를 균형 있게 설명하면 우수하다.",
        source_material_ids=[MATERIAL_ID],
    )
    exam.criteria[0].id = CRITERION_ID
    return exam


def make_exam_result_evaluation_job(
    *,
    payload: dict[str, str] | None = None,
    requested_by: UUID = STUDENT_ID,
) -> AsyncJob:
    return AsyncJob.enqueue(
        job_type=AsyncJobType.EXAM_RESULT_EVALUATION,
        target_type=AsyncJobTargetType.EXAM,
        target_id=EXAM_ID,
        requested_by=requested_by,
        payload=payload
        or {
            "exam_id": str(EXAM_ID),
            "session_id": str(SESSION_ID),
            "student_id": str(STUDENT_ID),
        },
        dedupe_key=f"exam-result-evaluation:{SESSION_ID}",
    )


@pytest.mark.asyncio
async def test_enqueue_returns_existing_active_job_when_dedupe_key_matches():
    repository = InMemoryAsyncJobRepository([
        AsyncJob.enqueue(
            job_type=AsyncJobType.EXAM_QUESTION_GENERATION,
            target_type=AsyncJobTargetType.EXAM,
            target_id=EXAM_ID,
            requested_by=JOB_REQUESTED_BY,
            payload={"exam_id": str(EXAM_ID)},
            dedupe_key="exam-question-generation:dedupe",
        )
    ])
    from app.async_job.application.service import AsyncJobService

    service = AsyncJobService(repository=repository)

    job = await service.enqueue(
        job_type=AsyncJobType.EXAM_QUESTION_GENERATION,
        target_type=AsyncJobTargetType.EXAM,
        target_id=EXAM_ID,
        requested_by=JOB_REQUESTED_BY,
        payload={"exam_id": str(EXAM_ID), "retry": True},
        dedupe_key="exam-question-generation:dedupe",
    )

    assert job is next(iter(repository.jobs.values()))
    assert len(repository.jobs) == 1
    assert repository.saved_job_ids == []


@pytest.mark.asyncio
async def test_enqueue_does_not_create_duplicate_active_jobs_when_requests_race():
    from app.async_job.application.service import AsyncJobService

    repository = InMemoryAsyncJobRepository()
    service = AsyncJobService(repository=repository)
    dedupe_key = "exam-result-evaluation:race"

    async def enqueue_job() -> AsyncJob:
        await asyncio.sleep(0)
        return await service.enqueue(
            job_type=AsyncJobType.EXAM_RESULT_EVALUATION,
            target_type=AsyncJobTargetType.EXAM,
            target_id=EXAM_ID,
            requested_by=JOB_REQUESTED_BY,
            payload={"exam_id": str(EXAM_ID), "session_id": str(SESSION_ID)},
            dedupe_key=dedupe_key,
        )

    first_job, second_job = await asyncio.gather(enqueue_job(), enqueue_job())

    active_jobs = [
        job
        for job in repository.jobs.values()
        if job.dedupe_key == dedupe_key
        and job.status in {AsyncJobStatus.QUEUED, AsyncJobStatus.RUNNING}
    ]

    assert first_job.id == second_job.id
    assert len(active_jobs) == 1


@pytest.mark.asyncio
async def test_run_next_queued_job_completes_material_ingest_job():
    job = make_material_ingest_job()
    material = make_material()
    file = make_file()
    ingest_port = FakeMaterialIngestPort(
        result=ClassroomMaterialIngestResult(
            scope_candidates=[
                ClassroomMaterialScopeCandidate(
                    label="기초 개념",
                    scope_text="머신러닝 개요",
                    keywords=["머신러닝"],
                    week_range="1주차",
                    confidence=0.9,
                )
            ]
        )
    )
    worker = AsyncJobWorker(
        repository=InMemoryAsyncJobRepository([job]),
        classroom_repository=InMemoryClassroomRepository([make_classroom()]),
        material_repository=InMemoryClassroomMaterialRepository([material]),
        file_usecase=FakeFileUseCase(files={FILE_ID: file}),
        material_ingest_port=ingest_port,
        exam_repository=InMemoryExamRepository([]),
        question_generation_port=None,
    )

    handled = await worker.run_next_queued_job()

    assert handled is True
    assert job.status is AsyncJobStatus.COMPLETED
    assert job.result["material_id"] == str(MATERIAL_ID)
    assert job.result["scope_candidate_count"] == 1
    assert material.ingest_status is ClassroomMaterialIngestStatus.COMPLETED
    assert len(ingest_port.requests) == 1
    assert ingest_port.requests[0].file_name == "week1.pdf"
    assert ingest_port.requests[0].content == b"pdf-content"


@pytest.mark.asyncio
async def test_run_next_queued_job_marks_material_ingest_job_failed():
    job = make_material_ingest_job()
    material = make_material()
    file = make_file()
    worker = AsyncJobWorker(
        repository=InMemoryAsyncJobRepository([job]),
        classroom_repository=InMemoryClassroomRepository([make_classroom()]),
        material_repository=InMemoryClassroomMaterialRepository([material]),
        file_usecase=FakeFileUseCase(files={FILE_ID: file}),
        material_ingest_port=FakeMaterialIngestPort(error=ClassroomMaterialIngestDomainException(message="qdrant unavailable")),
        exam_repository=InMemoryExamRepository([]),
        question_generation_port=None,
    )

    handled = await worker.run_next_queued_job()

    assert handled is True
    assert job.status is AsyncJobStatus.FAILED
    assert job.error_message == "qdrant unavailable"
    assert material.ingest_status is ClassroomMaterialIngestStatus.FAILED
    assert material.ingest_error == "qdrant unavailable"


@pytest.mark.asyncio
async def test_build_material_ingest_request_allows_public_https_link():
    material = make_link_material(source_url="https://example.com/lecture/week1")
    worker = AsyncJobWorker(
        repository=InMemoryAsyncJobRepository([]),
        classroom_repository=InMemoryClassroomRepository([]),
        material_repository=InMemoryClassroomMaterialRepository([material]),
        file_usecase=FakeFileUseCase(),
        material_ingest_port=FakeMaterialIngestPort(),
        exam_repository=InMemoryExamRepository([]),
        question_generation_port=None,
    )

    request = await worker._build_material_ingest_request(
        classroom_id=CLASSROOM_ID,
        material=material,
        file=None,
    )

    assert request.source_kind is ClassroomMaterialSourceKind.LINK
    assert request.source_url == material.source_url
    assert request.file_name == material.source_url
    assert request.content == material.source_url.encode()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "source_url",
    [
        "http://127.0.0.1/admin",
        "http://localhost/internal",
        "http://10.0.0.5/secret",
        "http://169.254.169.254/latest/meta-data",
        "file:///etc/passwd",
        "gopher://internal.service",
    ],
)
async def test_run_next_queued_job_fails_link_ingest_for_blocked_source_url(
    source_url: str,
):
    job = make_material_ingest_job()
    material = make_link_material(source_url=source_url)
    ingest_port = FakeMaterialIngestPort()
    worker = AsyncJobWorker(
        repository=InMemoryAsyncJobRepository([job]),
        classroom_repository=InMemoryClassroomRepository([make_classroom()]),
        material_repository=InMemoryClassroomMaterialRepository([material]),
        file_usecase=FakeFileUseCase(),
        material_ingest_port=ingest_port,
        exam_repository=InMemoryExamRepository([]),
        question_generation_port=None,
    )

    handled = await worker.run_next_queued_job()

    assert handled is True
    assert job.status is AsyncJobStatus.FAILED
    assert material.ingest_status is ClassroomMaterialIngestStatus.FAILED
    assert ingest_port.requests == []


@pytest.mark.asyncio
async def test_run_next_queued_job_persists_material_state_before_external_call():
    events: list[str] = []
    job = make_material_ingest_job()
    material = make_material()
    file = make_file()
    repository = InMemoryAsyncJobRepository([job])
    material_repository = InMemoryClassroomMaterialRepository([material])
    original_job_save = repository.save
    original_material_save = material_repository.save

    async def traced_job_save(entity: AsyncJob) -> None:
        events.append(f"save_job:{entity.status.value}")
        await original_job_save(entity)

    async def traced_material_save(entity: ClassroomMaterial) -> None:
        events.append(f"save_material:{entity.ingest_status.value}")
        await original_material_save(entity)

    repository.save = traced_job_save
    material_repository.save = traced_material_save

    file_usecase = FakeFileUseCase(files={FILE_ID: file})
    file_usecase.events = events
    ingest_port = FakeMaterialIngestPort(
        result=ClassroomMaterialIngestResult(scope_candidates=[]),
        events=events,
    )
    worker = AsyncJobWorker(
        repository=repository,
        classroom_repository=InMemoryClassroomRepository([make_classroom()]),
        material_repository=material_repository,
        file_usecase=file_usecase,
        material_ingest_port=ingest_port,
        exam_repository=InMemoryExamRepository([]),
        question_generation_port=None,
    )

    await worker.run_next_queued_job()

    assert events.index("save_job:running") < events.index(f"get_file:{FILE_ID}")
    assert events.index(f"get_file:{FILE_ID}") < events.index("save_material:pending")
    assert events.index("save_material:pending") < events.index(f"get_file_download:{FILE_ID}")
    assert events.index(f"get_file_download:{FILE_ID}") < events.index("ingest_material")


@pytest.mark.asyncio
async def test_run_next_queued_job_marks_material_failed_when_file_lookup_fails_before_pending():
    job = make_material_ingest_job()
    material = make_material()
    worker = AsyncJobWorker(
        repository=InMemoryAsyncJobRepository([job]),
        classroom_repository=InMemoryClassroomRepository([make_classroom()]),
        material_repository=InMemoryClassroomMaterialRepository([material]),
        file_usecase=FakeFileUseCase(files={}),
        material_ingest_port=FakeMaterialIngestPort(),
        exam_repository=InMemoryExamRepository([]),
        question_generation_port=None,
    )

    handled = await worker.run_next_queued_job()

    assert handled is True
    assert job.status is AsyncJobStatus.FAILED
    assert material.ingest_status is ClassroomMaterialIngestStatus.FAILED
    assert material.ingest_error == "강의 자료 적재 중 오류가 발생했습니다."


@pytest.mark.asyncio
async def test_run_next_queued_job_completes_exam_generation_job():
    job = make_exam_generation_job()
    exam = make_exam()
    material = make_completed_material()
    file = make_file()
    generation_port = FakeExamQuestionGenerationPort(
        drafts=[
            GeneratedExamQuestionDraft(
                question_number=1,
                max_score=1.0,
                question_type=ExamQuestionType.ORAL,
                bloom_level=BloomLevel.APPLY,
                difficulty=ExamDifficulty.MEDIUM,
                question_text="회귀와 분류의 차이를 설명하세요.",
                intent_text="1주차 머신러닝 기초 범위에서 지도학습 구분 이해를 확인하는 문항",
                rubric_text="출력 형태와 목적 차이를 설명하고 핵심 개념을 포함하면 정답",
                source_material_ids=[MATERIAL_ID],
            )
        ]
    )
    worker = AsyncJobWorker(
        repository=InMemoryAsyncJobRepository([job]),
        classroom_repository=InMemoryClassroomRepository([make_classroom()]),
        material_repository=InMemoryClassroomMaterialRepository([material]),
        file_usecase=FakeFileUseCase(files={FILE_ID: file}),
        material_ingest_port=None,
        exam_repository=InMemoryExamRepository([exam]),
        question_generation_port=generation_port,
    )

    handled = await worker.run_next_queued_job()

    assert handled is True
    assert job.status is AsyncJobStatus.COMPLETED
    assert job.result["exam_id"] == str(EXAM_ID)
    assert job.result["question_count"] == 1
    assert exam.generation_status is ExamGenerationStatus.COMPLETED
    assert len(exam.questions) == 1
    assert exam.questions[0].question_type is ExamQuestionType.ORAL
    assert len(generation_port.requests) == 1
    assert generation_port.requests[0].source_materials[0].file_name == "week1.pdf"
    assert generation_port.requests[0].question_type_counts[0].question_type is ExamQuestionType.ORAL
    assert generation_port.requests[0].question_type_counts[0].count == 1


@pytest.mark.asyncio
async def test_run_next_queued_job_marks_exam_generation_job_failed():
    job = make_exam_generation_job()
    exam = make_exam()
    material = make_completed_material()
    file = make_file()
    worker = AsyncJobWorker(
        repository=InMemoryAsyncJobRepository([job]),
        classroom_repository=InMemoryClassroomRepository([make_classroom()]),
        material_repository=InMemoryClassroomMaterialRepository([material]),
        file_usecase=FakeFileUseCase(files={FILE_ID: file}),
        material_ingest_port=None,
        exam_repository=InMemoryExamRepository([exam]),
        question_generation_port=FakeExamQuestionGenerationPort(error=ExamQuestionGenerationFailedException()),
    )

    handled = await worker.run_next_queued_job()

    assert handled is True
    assert job.status is AsyncJobStatus.FAILED
    assert job.error_message == "AI가 유효한 문항을 생성하지 못했습니다. 다시 시도해주세요."
    assert exam.generation_status is ExamGenerationStatus.FAILED
    assert exam.generation_error == job.error_message


@pytest.mark.asyncio
async def test_run_next_queued_job_sanitizes_long_unexpected_exam_generation_errors():
    long_error_message = "x" * 1500
    job = make_exam_generation_job()
    exam = make_exam()
    material = make_completed_material()
    file = make_file()
    worker = AsyncJobWorker(
        repository=InMemoryAsyncJobRepository([job]),
        classroom_repository=InMemoryClassroomRepository([make_classroom()]),
        material_repository=InMemoryClassroomMaterialRepository([material]),
        file_usecase=FakeFileUseCase(files={FILE_ID: file}),
        material_ingest_port=None,
        exam_repository=InMemoryExamRepository([exam]),
        question_generation_port=FakeExamQuestionGenerationPort(error=RuntimeError(long_error_message)),
    )

    handled = await worker.run_next_queued_job()

    assert handled is True
    assert job.status is AsyncJobStatus.FAILED
    assert job.error_message == "비동기 작업 처리 중 오류가 발생했습니다."
    assert exam.generation_status is ExamGenerationStatus.FAILED
    assert exam.generation_error == job.error_message


@pytest.mark.asyncio
async def test_run_next_queued_job_sanitizes_unexpected_exam_generation_errors():
    job = make_exam_generation_job()
    exam = make_exam()
    material = make_completed_material()
    file = make_file()
    worker = AsyncJobWorker(
        repository=InMemoryAsyncJobRepository([job]),
        classroom_repository=InMemoryClassroomRepository([make_classroom()]),
        material_repository=InMemoryClassroomMaterialRepository([material]),
        file_usecase=FakeFileUseCase(files={FILE_ID: file}),
        material_ingest_port=None,
        exam_repository=InMemoryExamRepository([exam]),
        question_generation_port=FakeExamQuestionGenerationPort(error=RuntimeError("database password leaked")),
    )

    handled = await worker.run_next_queued_job()

    assert handled is True
    assert job.status is AsyncJobStatus.FAILED
    assert job.error_message == "비동기 작업 처리 중 오류가 발생했습니다."
    assert exam.generation_error == job.error_message


@pytest.mark.asyncio
async def test_run_next_queued_job_persists_exam_running_before_generation_call():
    events: list[str] = []
    job = make_exam_generation_job()
    exam = make_exam()
    material = make_completed_material()
    file = make_file()
    repository = InMemoryAsyncJobRepository([job])
    exam_repository = InMemoryExamRepository([exam])
    exam_repository.events = events
    original_job_save = repository.save

    async def traced_job_save(entity: AsyncJob) -> None:
        events.append(f"save_job:{entity.status.value}")
        await original_job_save(entity)

    repository.save = traced_job_save
    generation_port = FakeExamQuestionGenerationPort(drafts=[], events=events)
    worker = AsyncJobWorker(
        repository=repository,
        classroom_repository=InMemoryClassroomRepository([make_classroom()]),
        material_repository=InMemoryClassroomMaterialRepository([material]),
        file_usecase=FakeFileUseCase(files={FILE_ID: file}),
        material_ingest_port=None,
        exam_repository=exam_repository,
        question_generation_port=generation_port,
    )

    await worker.run_next_queued_job()

    assert events.index("save_job:running") < events.index("save_exam:running")
    assert events.index("save_exam:running") < events.index("generate_questions")


@pytest.mark.asyncio
async def test_run_next_queued_job_completes_exam_result_evaluation_job():
    job = make_exam_result_evaluation_job()
    exam = make_exam_for_evaluation()
    session = make_completed_session()
    result = make_pending_result()
    turn = make_turn()
    evaluation_port = FakeExamResultEvaluationPort(
        result=EvaluateExamResult(
            summary="핵심 개념은 이해했지만 예시 설명은 보완이 필요합니다.",
            strengths=["지도학습의 정의를 정확히 설명했습니다."],
            weaknesses=["대표 알고리즘 예시가 부족했습니다."],
            improvement_suggestions=["분류와 회귀 예시를 함께 연습하세요."],
            criteria_results=[
                ExamResultEvaluationCriterionScore(
                    criterion_id=CRITERION_ID,
                    score=87.5,
                    feedback="핵심 개념 설명은 정확하지만 적용 예시가 다소 부족합니다.",
                )
            ],
        )
    )
    worker = AsyncJobWorker(
        repository=InMemoryAsyncJobRepository([job]),
        classroom_repository=InMemoryClassroomRepository([make_classroom()]),
        material_repository=InMemoryClassroomMaterialRepository([]),
        file_usecase=FakeFileUseCase(),
        material_ingest_port=None,
        exam_repository=InMemoryExamRepository([exam]),
        question_generation_port=None,
        exam_session_repository=InMemoryExamSessionRepository([session]),
        exam_result_repository=InMemoryExamResultRepository([result]),
        exam_turn_repository=InMemoryExamTurnRepository([turn]),
        result_evaluation_port=evaluation_port,
    )

    handled = await worker.run_next_queued_job()

    assert handled is True
    assert job.status is AsyncJobStatus.COMPLETED
    assert job.result["exam_id"] == str(EXAM_ID)
    assert job.result["session_id"] == str(SESSION_ID)
    assert job.result["result_id"] == str(RESULT_ID)
    assert job.result["status"] == ExamResultStatus.COMPLETED.value
    assert result.status is ExamResultStatus.COMPLETED
    assert result.overall_score == 87.5
    assert result.summary == "핵심 개념은 이해했지만 예시 설명은 보완이 필요합니다."
    assert result.strengths == ["지도학습의 정의를 정확히 설명했습니다."]
    assert result.weaknesses == ["대표 알고리즘 예시가 부족했습니다."]
    assert result.improvement_suggestions == ["분류와 회귀 예시를 함께 연습하세요."]
    assert len(result.criteria_results) == 1
    assert result.criteria_results[0].criterion_id == CRITERION_ID
    assert result.criteria_results[0].score == 87.5
    assert len(evaluation_port.requests) == 1
    request = evaluation_port.requests[0]
    assert request.exam_id == EXAM_ID
    assert request.session_id == SESSION_ID
    assert request.student_id == STUDENT_ID
    assert request.exam_title == exam.title
    assert request.exam_type is exam.exam_type
    assert len(request.criteria) == 1
    assert request.criteria[0].criterion_id == CRITERION_ID
    assert len(request.questions) == 1
    assert request.questions[0].max_score == exam.questions[0].max_score
    assert request.questions[0].intent_text == exam.questions[0].intent_text
    assert request.questions[0].answer_options == exam.questions[0].answer_options
    assert request.questions[0].correct_answer_text == exam.questions[0].correct_answer_text
    assert len(request.turns) == 1
    assert request.turns[0].content == turn.content
    assert request.turns[0].metadata == turn.metadata


@pytest.mark.asyncio
async def test_run_next_queued_job_skips_exam_result_evaluation_when_completed_result_appears_during_result_lock():
    job = make_exam_result_evaluation_job()
    exam = make_exam_for_evaluation()
    session = make_completed_session()
    result = make_pending_result()
    turn = make_turn()
    result_repository = CompletedResultAppearsDuringResultLockRepository([result])
    evaluation_port = FakeExamResultEvaluationPort()
    worker = AsyncJobWorker(
        repository=InMemoryAsyncJobRepository([job]),
        classroom_repository=InMemoryClassroomRepository([make_classroom()]),
        material_repository=InMemoryClassroomMaterialRepository([]),
        file_usecase=FakeFileUseCase(),
        material_ingest_port=None,
        exam_repository=InMemoryExamRepository([exam]),
        question_generation_port=None,
        exam_session_repository=InMemoryExamSessionRepository([session]),
        exam_result_repository=result_repository,
        exam_turn_repository=InMemoryExamTurnRepository([turn]),
        result_evaluation_port=evaluation_port,
    )

    handled = await worker.run_next_queued_job()

    assert handled is True
    assert result_repository.completed_result_injected is True
    assert job.status is AsyncJobStatus.COMPLETED
    assert job.result["result_id"] == str(RESULT_ID)
    assert job.result["status"] == ExamResultStatus.COMPLETED.value
    assert result.status is ExamResultStatus.COMPLETED
    assert evaluation_port.requests == []


@pytest.mark.asyncio
async def test_run_next_queued_job_skips_exam_result_evaluation_when_result_completes_after_evaluation():
    job = make_exam_result_evaluation_job()
    exam = make_exam_for_evaluation()
    session = make_completed_session()
    result = make_pending_result()
    turn = make_turn()
    result_repository = CompletedResultAppearsAfterEvaluationRepository([result])
    evaluation_port = FakeExamResultEvaluationPort()
    worker = AsyncJobWorker(
        repository=InMemoryAsyncJobRepository([job]),
        classroom_repository=InMemoryClassroomRepository([make_classroom()]),
        material_repository=InMemoryClassroomMaterialRepository([]),
        file_usecase=FakeFileUseCase(),
        material_ingest_port=None,
        exam_repository=InMemoryExamRepository([exam]),
        question_generation_port=None,
        exam_session_repository=InMemoryExamSessionRepository([session]),
        exam_result_repository=result_repository,
        exam_turn_repository=InMemoryExamTurnRepository([turn]),
        result_evaluation_port=evaluation_port,
    )

    handled = await worker.run_next_queued_job()

    assert handled is True
    assert result_repository.completed_result_injected is True
    assert result_repository.lock_call_count == 2
    assert result_repository.seen_student_ids == [STUDENT_ID, STUDENT_ID]
    assert job.status is AsyncJobStatus.COMPLETED
    assert job.result["result_id"] == str(RESULT_ID)
    assert job.result["status"] == ExamResultStatus.COMPLETED.value
    assert result.status is ExamResultStatus.COMPLETED
    assert result.overall_score is None
    assert result.summary is None
    assert result.criteria_results == []
    assert evaluation_port.requests != []


@pytest.mark.asyncio
async def test_run_next_queued_job_uses_payload_student_id_for_completion_reload():
    requested_by = JOB_REQUESTED_BY
    payload_student_id = STUDENT_ID
    job = make_exam_result_evaluation_job(requested_by=requested_by)
    exam = make_exam_for_evaluation()
    session = make_completed_session()
    result = make_pending_result()
    turn = make_turn()
    result_repository = CompletedResultAppearsAfterEvaluationRepository([result])
    evaluation_port = FakeExamResultEvaluationPort()
    worker = AsyncJobWorker(
        repository=InMemoryAsyncJobRepository([job]),
        classroom_repository=InMemoryClassroomRepository([make_classroom()]),
        material_repository=InMemoryClassroomMaterialRepository([]),
        file_usecase=FakeFileUseCase(),
        material_ingest_port=None,
        exam_repository=InMemoryExamRepository([exam]),
        question_generation_port=None,
        exam_session_repository=InMemoryExamSessionRepository([session]),
        exam_result_repository=result_repository,
        exam_turn_repository=InMemoryExamTurnRepository([turn]),
        result_evaluation_port=evaluation_port,
    )

    handled = await worker.run_next_queued_job()

    assert handled is True
    assert requested_by != payload_student_id
    assert result_repository.seen_student_ids == [
        payload_student_id,
        payload_student_id,
    ]
    assert job.status is AsyncJobStatus.COMPLETED


@pytest.mark.asyncio
async def test_run_next_queued_job_computes_weighted_exam_result_score():
    job = make_exam_result_evaluation_job()
    exam = make_exam_for_evaluation()
    exam.criteria[0].weight = 70
    second_criterion_id = UUID("cccccccc-cccc-cccc-cccc-cccccccccccc")
    exam.criteria.append(
        ExamCriterion(
            exam_id=exam.id,
            title="적용 능력",
            description="개념을 예시에 적용하는지 평가",
            weight=30,
            sort_order=2,
        )
    )
    exam.criteria[1].id = second_criterion_id
    session = make_completed_session()
    result = make_pending_result()
    turn = make_turn()
    evaluation_port = FakeExamResultEvaluationPort(
        result=EvaluateExamResult(
            summary="가중치 기반 평가가 완료되었습니다.",
            strengths=["핵심 개념 설명이 우수합니다."],
            weaknesses=["적용 예시 근거가 부족합니다."],
            improvement_suggestions=["사례 기반 설명을 연습하세요."],
            criteria_results=[
                ExamResultEvaluationCriterionScore(
                    criterion_id=CRITERION_ID,
                    score=100,
                    feedback="핵심 개념 설명이 정확합니다.",
                ),
                ExamResultEvaluationCriterionScore(
                    criterion_id=second_criterion_id,
                    score=50,
                    feedback="적용 예시 설명이 부족합니다.",
                ),
            ],
        )
    )
    worker = AsyncJobWorker(
        repository=InMemoryAsyncJobRepository([job]),
        classroom_repository=InMemoryClassroomRepository([make_classroom()]),
        material_repository=InMemoryClassroomMaterialRepository([]),
        file_usecase=FakeFileUseCase(),
        material_ingest_port=None,
        exam_repository=InMemoryExamRepository([exam]),
        question_generation_port=None,
        exam_session_repository=InMemoryExamSessionRepository([session]),
        exam_result_repository=InMemoryExamResultRepository([result]),
        exam_turn_repository=InMemoryExamTurnRepository([turn]),
        result_evaluation_port=evaluation_port,
    )

    handled = await worker.run_next_queued_job()

    assert handled is True
    assert result.status is ExamResultStatus.COMPLETED
    assert result.overall_score == 85


@pytest.mark.asyncio
async def test_run_next_queued_job_marks_exam_result_evaluation_failed_for_missing_criterion_scores():
    job = make_exam_result_evaluation_job()
    exam = make_exam_for_evaluation()
    exam.criteria[0].weight = 70
    second_criterion_id = UUID("cccccccc-cccc-cccc-cccc-cccccccccccc")
    exam.criteria.append(
        ExamCriterion(
            exam_id=exam.id,
            title="적용 능력",
            description="개념을 예시에 적용하는지 평가",
            weight=30,
            sort_order=2,
        )
    )
    exam.criteria[1].id = second_criterion_id
    session = make_completed_session()
    result = make_pending_result()
    turn = make_turn()
    evaluation_port = FakeExamResultEvaluationPort(
        result=EvaluateExamResult(
            summary="부분 평가 응답",
            strengths=[],
            weaknesses=[],
            improvement_suggestions=[],
            criteria_results=[
                ExamResultEvaluationCriterionScore(
                    criterion_id=CRITERION_ID,
                    score=90,
                    feedback="핵심 개념 설명은 좋습니다.",
                )
            ],
        )
    )
    worker = AsyncJobWorker(
        repository=InMemoryAsyncJobRepository([job]),
        classroom_repository=InMemoryClassroomRepository([make_classroom()]),
        material_repository=InMemoryClassroomMaterialRepository([]),
        file_usecase=FakeFileUseCase(),
        material_ingest_port=None,
        exam_repository=InMemoryExamRepository([exam]),
        question_generation_port=None,
        exam_session_repository=InMemoryExamSessionRepository([session]),
        exam_result_repository=InMemoryExamResultRepository([result]),
        exam_turn_repository=InMemoryExamTurnRepository([turn]),
        result_evaluation_port=evaluation_port,
    )

    handled = await worker.run_next_queued_job()

    assert handled is True
    assert job.status is AsyncJobStatus.FAILED
    assert job.error_message == "비동기 작업 처리 중 오류가 발생했습니다."
    assert result.status is ExamResultStatus.PENDING


@pytest.mark.asyncio
async def test_run_next_queued_job_completes_exam_result_evaluation_with_quantitative_multiple_choice_full_credit():
    job = make_exam_result_evaluation_job()
    exam = make_multiple_choice_exam_for_evaluation()
    session = make_completed_session()
    result = make_pending_result()
    turn = make_turn(
        content="정답 레이블이 있는 데이터로 학습한다.",
        metadata={"question_number": "1"},
    )
    evaluation_port = FakeExamResultEvaluationPort()
    worker = AsyncJobWorker(
        repository=InMemoryAsyncJobRepository([job]),
        classroom_repository=InMemoryClassroomRepository([make_classroom()]),
        material_repository=InMemoryClassroomMaterialRepository([]),
        file_usecase=FakeFileUseCase(),
        material_ingest_port=None,
        exam_repository=InMemoryExamRepository([exam]),
        question_generation_port=None,
        exam_session_repository=InMemoryExamSessionRepository([session]),
        exam_result_repository=InMemoryExamResultRepository([result]),
        exam_turn_repository=InMemoryExamTurnRepository([turn]),
        result_evaluation_port=evaluation_port,
    )

    handled = await worker.run_next_queued_job()

    assert handled is True
    assert job.status is AsyncJobStatus.COMPLETED
    assert result.status is ExamResultStatus.COMPLETED
    assert result.overall_score == 100
    assert result.summary == "객관식/주관식 1문항 중 1문항을 맞혀 일반 정량 점수로 반영했습니다."
    assert len(result.criteria_results) == 1
    assert result.criteria_results[0].criterion_id == CRITERION_ID
    assert result.criteria_results[0].score == 100
    assert evaluation_port.requests == []


@pytest.mark.asyncio
async def test_run_next_queued_job_completes_exam_result_evaluation_with_quantitative_subjective_full_credit():
    job = make_exam_result_evaluation_job()
    exam = make_subjective_exam_for_evaluation()
    session = make_completed_session()
    result = make_pending_result()
    turn = make_turn(
        content="  레이블 데이터  ",
        metadata={"question_number": "1"},
    )
    evaluation_port = FakeExamResultEvaluationPort()
    worker = AsyncJobWorker(
        repository=InMemoryAsyncJobRepository([job]),
        classroom_repository=InMemoryClassroomRepository([make_classroom()]),
        material_repository=InMemoryClassroomMaterialRepository([]),
        file_usecase=FakeFileUseCase(),
        material_ingest_port=None,
        exam_repository=InMemoryExamRepository([exam]),
        question_generation_port=None,
        exam_session_repository=InMemoryExamSessionRepository([session]),
        exam_result_repository=InMemoryExamResultRepository([result]),
        exam_turn_repository=InMemoryExamTurnRepository([turn]),
        result_evaluation_port=evaluation_port,
    )

    handled = await worker.run_next_queued_job()

    assert handled is True
    assert job.status is AsyncJobStatus.COMPLETED
    assert result.status is ExamResultStatus.COMPLETED
    assert result.overall_score == 100
    assert len(result.criteria_results) == 1
    assert result.criteria_results[0].score == 100
    assert evaluation_port.requests == []


@pytest.mark.asyncio
async def test_run_next_queued_job_scores_subjective_with_exact_answer_without_llm_evaluation():
    job = make_exam_result_evaluation_job()
    exam = make_subjective_exam_for_evaluation()
    session = make_completed_session()
    result = make_pending_result()
    turn = make_turn(
        content="레이블 데이터",
        metadata={"question_number": "1"},
    )
    evaluation_port = FakeExamResultEvaluationPort()
    worker = AsyncJobWorker(
        repository=InMemoryAsyncJobRepository([job]),
        classroom_repository=InMemoryClassroomRepository([make_classroom()]),
        material_repository=InMemoryClassroomMaterialRepository([]),
        file_usecase=FakeFileUseCase(),
        material_ingest_port=None,
        exam_repository=InMemoryExamRepository([exam]),
        question_generation_port=None,
        exam_session_repository=InMemoryExamSessionRepository([session]),
        exam_result_repository=InMemoryExamResultRepository([result]),
        exam_turn_repository=InMemoryExamTurnRepository([turn]),
        result_evaluation_port=evaluation_port,
    )

    handled = await worker.run_next_queued_job()

    assert handled is True
    assert job.status is AsyncJobStatus.COMPLETED
    assert result.overall_score == 100
    assert len(evaluation_port.requests) == 0


@pytest.mark.asyncio
async def test_run_next_queued_job_keeps_objective_only_criteria_when_merging_results():
    job = make_exam_result_evaluation_job()
    exam = make_mixed_exam_for_evaluation()
    session = make_completed_session()
    result = make_pending_result()
    turns = [
        make_turn(
            content="정답 레이블이 있는 데이터로 학습한다.",
            metadata={"question_number": "1"},
        ),
        ExamTurn.create(
            session_id=SESSION_ID,
            sequence=2,
            role=ExamTurnRole.STUDENT,
            event_type=ExamTurnEventType.ANSWER,
            content="설명형 답변",
            created_at=datetime(2026, 4, 1, 9, 40, tzinfo=UTC),
            metadata={"question_number": "2"},
        ),
    ]
    turns[1].id = UUID("abababab-abab-abab-abab-abababababab")
    objective_only_criterion_id = UUID("cdcdcdcd-cdcd-cdcd-cdcd-cdcdcdcdcdcd")
    exam.criteria.append(
        ExamCriterion(
            exam_id=exam.id,
            title="추가 기준",
            description=None,
            weight=20,
            sort_order=2,
            excellent_definition="정확함",
            average_definition=None,
            poor_definition=None,
        )
    )
    exam.criteria[1].id = objective_only_criterion_id
    evaluation_port = FakeExamResultEvaluationPort(
        result=EvaluateExamResult(
            summary="구술형 평가가 완료되었습니다.",
            strengths=[],
            weaknesses=[],
            improvement_suggestions=[],
            criteria_results=[
                ExamResultEvaluationCriterionScore(
                    criterion_id=CRITERION_ID,
                    score=80,
                    feedback="구술형 반영",
                )
            ],
        )
    )
    worker = AsyncJobWorker(
        repository=InMemoryAsyncJobRepository([job]),
        classroom_repository=InMemoryClassroomRepository([make_classroom()]),
        material_repository=InMemoryClassroomMaterialRepository([]),
        file_usecase=FakeFileUseCase(),
        material_ingest_port=None,
        exam_repository=InMemoryExamRepository([exam]),
        question_generation_port=None,
        exam_session_repository=InMemoryExamSessionRepository([session]),
        exam_result_repository=InMemoryExamResultRepository([result]),
        exam_turn_repository=InMemoryExamTurnRepository(turns),
        result_evaluation_port=evaluation_port,
    )

    handled = await worker.run_next_queued_job()

    assert handled is True
    criterion_ids = {item.criterion_id for item in result.criteria_results}
    assert objective_only_criterion_id in criterion_ids


@pytest.mark.asyncio
async def test_run_next_queued_job_scores_zero_without_llm_when_objective_metadata_missing():
    job = make_exam_result_evaluation_job()
    exam = make_multiple_choice_exam_for_evaluation()
    session = make_completed_session()
    result = make_pending_result()
    turn = make_turn(content="정답 레이블이 있는 데이터로 학습한다.")
    evaluation_port = FakeExamResultEvaluationPort()
    worker = AsyncJobWorker(
        repository=InMemoryAsyncJobRepository([job]),
        classroom_repository=InMemoryClassroomRepository([make_classroom()]),
        material_repository=InMemoryClassroomMaterialRepository([]),
        file_usecase=FakeFileUseCase(),
        material_ingest_port=None,
        exam_repository=InMemoryExamRepository([exam]),
        question_generation_port=None,
        exam_session_repository=InMemoryExamSessionRepository([session]),
        exam_result_repository=InMemoryExamResultRepository([result]),
        exam_turn_repository=InMemoryExamTurnRepository([turn]),
        result_evaluation_port=evaluation_port,
    )

    handled = await worker.run_next_queued_job()

    assert handled is True
    assert job.status is AsyncJobStatus.COMPLETED
    assert result.status is ExamResultStatus.COMPLETED
    assert result.overall_score == 0
    assert result.summary == "객관식/주관식 1문항 중 0문항을 맞혀 일반 정량 점수로 반영했습니다."
    assert len(evaluation_port.requests) == 0


@pytest.mark.asyncio
async def test_run_next_queued_job_scores_objective_wrong_answer_without_llm_fallback():
    job = make_exam_result_evaluation_job()
    exam = make_subjective_exam_for_evaluation()
    session = make_completed_session()
    result = make_pending_result()
    turn = make_turn(
        content="틀린 답",
        metadata={"question_number": "1"},
    )
    evaluation_port = FakeExamResultEvaluationPort()
    worker = AsyncJobWorker(
        repository=InMemoryAsyncJobRepository([job]),
        classroom_repository=InMemoryClassroomRepository([make_classroom()]),
        material_repository=InMemoryClassroomMaterialRepository([]),
        file_usecase=FakeFileUseCase(),
        material_ingest_port=None,
        exam_repository=InMemoryExamRepository([exam]),
        question_generation_port=None,
        exam_session_repository=InMemoryExamSessionRepository([session]),
        exam_result_repository=InMemoryExamResultRepository([result]),
        exam_turn_repository=InMemoryExamTurnRepository([turn]),
        result_evaluation_port=evaluation_port,
    )

    handled = await worker.run_next_queued_job()

    assert handled is True
    assert job.status is AsyncJobStatus.COMPLETED
    assert result.status is ExamResultStatus.COMPLETED
    assert result.overall_score == 0
    assert len(evaluation_port.requests) == 0


@pytest.mark.asyncio
async def test_run_next_queued_job_combines_objective_quantitative_and_oral_rubric_scores():
    job = make_exam_result_evaluation_job()
    exam = make_mixed_exam_for_evaluation()
    session = make_completed_session()
    result = make_pending_result()
    turns = [
        make_turn(
            content="정답 레이블이 있는 데이터로 학습한다.",
            metadata={"question_number": "1"},
        ),
        ExamTurn.create(
            session_id=SESSION_ID,
            sequence=2,
            role=ExamTurnRole.STUDENT,
            event_type=ExamTurnEventType.ANSWER,
            content="장점은 정확한 지도 신호를 활용하는 것이고 단점은 레이블 비용이 큽니다.",
            created_at=datetime(2026, 4, 1, 9, 40, tzinfo=UTC),
            metadata={"question_number": "2"},
        ),
    ]
    turns[1].id = UUID("abababab-abab-abab-abab-abababababab")
    evaluation_port = FakeExamResultEvaluationPort(
        result=EvaluateExamResult(
            summary="구술형 평가가 완료되었습니다.",
            strengths=["구술형 설명이 구체적입니다."],
            weaknesses=[],
            improvement_suggestions=[],
            criteria_results=[
                ExamResultEvaluationCriterionScore(
                    criterion_id=CRITERION_ID,
                    score=80,
                    feedback="구술형 답변이 전반적으로 우수합니다.",
                )
            ],
        )
    )
    worker = AsyncJobWorker(
        repository=InMemoryAsyncJobRepository([job]),
        classroom_repository=InMemoryClassroomRepository([make_classroom()]),
        material_repository=InMemoryClassroomMaterialRepository([]),
        file_usecase=FakeFileUseCase(),
        material_ingest_port=None,
        exam_repository=InMemoryExamRepository([exam]),
        question_generation_port=None,
        exam_session_repository=InMemoryExamSessionRepository([session]),
        exam_result_repository=InMemoryExamResultRepository([result]),
        exam_turn_repository=InMemoryExamTurnRepository(turns),
        result_evaluation_port=evaluation_port,
    )

    handled = await worker.run_next_queued_job()

    assert handled is True
    assert job.status is AsyncJobStatus.COMPLETED
    assert result.status is ExamResultStatus.COMPLETED
    assert result.overall_score == 90
    assert result.summary == "객관식/주관식 1문항 중 1문항을 맞혀 일반 정량 점수로 반영했습니다. 구술형 문항은 루브릭 평가를 함께 반영했습니다."
    assert len(evaluation_port.requests) == 1
    assert len(evaluation_port.requests[0].questions) == 1
    assert evaluation_port.requests[0].questions[0].question_type is ExamQuestionType.ORAL


@pytest.mark.asyncio
async def test_run_next_queued_job_marks_exam_result_evaluation_failed_for_invalid_payload():
    job = make_exam_result_evaluation_job(payload={"exam_id": str(EXAM_ID)})
    evaluation_port = FakeExamResultEvaluationPort()
    worker = AsyncJobWorker(
        repository=InMemoryAsyncJobRepository([job]),
        classroom_repository=InMemoryClassroomRepository([make_classroom()]),
        material_repository=InMemoryClassroomMaterialRepository([]),
        file_usecase=FakeFileUseCase(),
        material_ingest_port=None,
        exam_repository=InMemoryExamRepository([make_exam_for_evaluation()]),
        question_generation_port=None,
        exam_session_repository=InMemoryExamSessionRepository([make_completed_session()]),
        exam_result_repository=InMemoryExamResultRepository([make_pending_result()]),
        exam_turn_repository=InMemoryExamTurnRepository([make_turn()]),
        result_evaluation_port=evaluation_port,
    )

    handled = await worker.run_next_queued_job()

    assert handled is True
    assert job.status is AsyncJobStatus.FAILED
    assert job.error_message == "비동기 작업 처리 중 오류가 발생했습니다."
    assert evaluation_port.requests == []


@pytest.mark.asyncio
async def test_run_next_queued_job_marks_exam_result_evaluation_failed_when_port_errors():
    class EvaluationFailedException(CustomException):
        code = 502
        error_code = "EXAM_RESULT_EVALUATION__FAILED"
        message = "자동 평가 생성에 실패했습니다."

    job = make_exam_result_evaluation_job()
    exam = make_exam_for_evaluation()
    session = make_completed_session()
    result = make_pending_result()
    turn = make_turn()
    worker = AsyncJobWorker(
        repository=InMemoryAsyncJobRepository([job]),
        classroom_repository=InMemoryClassroomRepository([make_classroom()]),
        material_repository=InMemoryClassroomMaterialRepository([]),
        file_usecase=FakeFileUseCase(),
        material_ingest_port=None,
        exam_repository=InMemoryExamRepository([exam]),
        question_generation_port=None,
        exam_session_repository=InMemoryExamSessionRepository([session]),
        exam_result_repository=InMemoryExamResultRepository([result]),
        exam_turn_repository=InMemoryExamTurnRepository([turn]),
        result_evaluation_port=FakeExamResultEvaluationPort(error=EvaluationFailedException()),
    )

    handled = await worker.run_next_queued_job()

    assert handled is True
    assert job.status is AsyncJobStatus.FAILED
    assert job.error_message == "자동 평가 생성에 실패했습니다."
    assert result.status is ExamResultStatus.PENDING
