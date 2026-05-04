import uuid
from contextvars import ContextVar
from datetime import UTC, datetime, timedelta
from uuid import UUID

import pytest
import pytest_asyncio
from sqlalchemy import delete, select, text
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_scoped_session,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import NullPool

import app.exam.application.service.exam as exam_service_module
import core.db.transactional as transactional_module
from app.auth.application.exception import AuthForbiddenException
from app.auth.domain.entity import CurrentUser
from app.classroom.adapter.output.persistence.sqlalchemy import (
    classroom as classroom_repo,
)
from app.classroom.adapter.output.persistence.sqlalchemy.classroom import (
    ClassroomSQLAlchemyRepository,
)
from app.classroom.domain.entity import Classroom
from app.exam.adapter.output.persistence.sqlalchemy import exam as exam_repo
from app.exam.adapter.output.persistence.sqlalchemy.exam import (
    ExamResultSQLAlchemyRepository,
    ExamSessionSQLAlchemyRepository,
    ExamSQLAlchemyRepository,
    ExamTurnSQLAlchemyRepository,
)
from app.exam.application.service import ExamService
from app.exam.domain.entity import (
    Exam,
    ExamCriterion,
    ExamResultStatus,
    ExamStatus,
    ExamType,
    RealtimeClientSecret,
)
from app.organization.adapter.output.persistence.sqlalchemy import (
    OrganizationSQLAlchemyRepository,
)
from app.organization.adapter.output.persistence.sqlalchemy import (
    organization as organization_repo,
)
from app.organization.domain.entity import (
    Organization,
    OrganizationAuthProvider,
)
from app.user.adapter.output.persistence.sqlalchemy import user as user_repo
from app.user.adapter.output.persistence.sqlalchemy.user import (
    UserSQLAlchemyRepository,
)
from app.user.domain.entity import User, UserRole
from core.config import config
from core.db.sqlalchemy import init_orm_mappers
from core.db.sqlalchemy.models.classroom import classroom_table
from core.db.sqlalchemy.models.exam import (
    exam_criterion_table,
    exam_result_table,
    exam_session_table,
    exam_table,
)
from core.db.sqlalchemy.models.organization import organization_table
from core.db.sqlalchemy.models.user import user_table

try:
    init_orm_mappers()
except Exception:
    pass

ORG_ID = UUID("11111111-1111-1111-1111-111111111111")
CLASSROOM_ID = UUID("22222222-2222-2222-2222-222222222222")
EXAM_ID = UUID("33333333-3333-3333-3333-333333333333")
PROFESSOR_ID = UUID("44444444-4444-4444-4444-444444444444")
STUDENT_ID = UUID("55555555-5555-5555-5555-555555555555")
NOW = datetime.now(UTC)
STARTS_AT = NOW - timedelta(minutes=5)
ENDS_AT = NOW + timedelta(hours=1)
SECRET_EXPIRES_AT = NOW + timedelta(minutes=55)


@pytest_asyncio.fixture(autouse=True)
async def setup_db():
    engine = create_async_engine(config.DATABASE_URL, poolclass=NullPool)
    async with engine.begin() as conn:
        await conn.execute(text("DROP TABLE IF EXISTS t_exam_result CASCADE"))
        await conn.execute(text("DROP TABLE IF EXISTS t_exam_session CASCADE"))
        await conn.execute(
            text("DROP TABLE IF EXISTS t_exam_criterion CASCADE")
        )
        await conn.execute(text("DROP TABLE IF EXISTS t_exam CASCADE"))
        await conn.execute(text("DROP TABLE IF EXISTS t_classroom CASCADE"))
        await conn.execute(text("DROP TABLE IF EXISTS t_user CASCADE"))
        await conn.execute(text("DROP TABLE IF EXISTS t_organization CASCADE"))
        await conn.run_sync(organization_table.create)
        await conn.run_sync(user_table.create)
        await conn.run_sync(classroom_table.create)
        await conn.run_sync(exam_table.create)
        await conn.run_sync(exam_criterion_table.create)
        await conn.run_sync(exam_session_table.create)
        await conn.run_sync(exam_result_table.create)
    yield
    async with engine.begin() as conn:
        await conn.execute(delete(exam_result_table))
        await conn.execute(delete(exam_session_table))
        await conn.execute(delete(exam_criterion_table))
        await conn.execute(delete(exam_table))
        await conn.execute(delete(classroom_table))
        await conn.execute(delete(user_table))
        await conn.execute(delete(organization_table))
    await engine.dispose()


@pytest_asyncio.fixture
async def db_session():
    session_context = ContextVar[str]("test_session_context", default="global")

    def get_context() -> str:
        return session_context.get()

    engine = create_async_engine(config.DATABASE_URL, poolclass=NullPool)
    factory = async_sessionmaker(
        bind=engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )
    scoped_session = async_scoped_session(factory, scopefunc=get_context)
    original_sessions = (
        organization_repo.session,
        user_repo.session,
        classroom_repo.session,
        exam_repo.session,
        exam_service_module.session,
        transactional_module.session,
    )
    organization_repo.session = scoped_session
    user_repo.session = scoped_session
    classroom_repo.session = scoped_session
    exam_repo.session = scoped_session
    exam_service_module.session = scoped_session
    transactional_module.session = scoped_session

    token = session_context.set(str(uuid.uuid4()))
    current_session = scoped_session()
    try:
        yield current_session
        await current_session.rollback()
    finally:
        (
            organization_repo.session,
            user_repo.session,
            classroom_repo.session,
            exam_repo.session,
            exam_service_module.session,
            transactional_module.session,
        ) = original_sessions
        await scoped_session.remove()
        await engine.dispose()
        session_context.reset(token)


class FakeClassroomUseCase:
    def __init__(self, classroom: Classroom):
        self.classroom = classroom

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


class FakeRealtimeSessionPort:
    def __init__(self):
        self.calls: list[str] = []

    async def create_client_secret(
        self,
        *,
        instructions: str,
    ) -> RealtimeClientSecret:
        self.calls.append(instructions)
        return RealtimeClientSecret(
            value="ek_test_secret",
            expires_at=SECRET_EXPIRES_AT,
            provider_session_id="sess_test_123",
        )


def make_current_user() -> CurrentUser:
    return CurrentUser(
        id=STUDENT_ID,
        organization_id=ORG_ID,
        login_id="20260001",
        role=UserRole.STUDENT,
    )


async def seed_exam_context(db_session: AsyncSession) -> Classroom:
    organization = Organization(
        code="univ_hansung",
        name="한성대학교",
        auth_provider=OrganizationAuthProvider.HANSUNG_SIS,
    )
    organization.id = ORG_ID
    await OrganizationSQLAlchemyRepository().save(organization)
    await db_session.flush()

    professor = User(
        organization_id=ORG_ID,
        login_id="professor01",
        role=UserRole.PROFESSOR,
        email="professor@example.com",
        name="교수",
    )
    professor.id = PROFESSOR_ID
    student = User(
        organization_id=ORG_ID,
        login_id="20260001",
        role=UserRole.STUDENT,
        email="student@example.com",
        name="학생",
    )
    student.id = STUDENT_ID
    await UserSQLAlchemyRepository().save(professor)
    await UserSQLAlchemyRepository().save(student)
    await db_session.flush()

    classroom = Classroom(
        organization_id=ORG_ID,
        name="AI 기초",
        professor_ids=[PROFESSOR_ID],
        grade=4,
        semester="1",
        section="01",
        description="캡스톤 시험 수업",
        student_ids=[STUDENT_ID],
    )
    classroom.id = CLASSROOM_ID
    await ClassroomSQLAlchemyRepository().save(classroom)
    await db_session.flush()

    exam = Exam(
        classroom_id=CLASSROOM_ID,
        title="중간 평가",
        description="1주차 범위 평가",
        exam_type=ExamType.MIDTERM,
        status=ExamStatus.READY,
        duration_minutes=60,
        starts_at=STARTS_AT,
        ends_at=ENDS_AT,
        max_attempts=1,
        week=1,
        criteria=[
            ExamCriterion(
                exam_id=EXAM_ID,
                title="개념 이해",
                description="핵심 개념을 설명하는지 평가",
                weight=100,
                sort_order=1,
                excellent_definition="개념 관계를 정확히 설명한다.",
                average_definition="개념 설명은 가능하나 연결이 약하다.",
                poor_definition="개념 이해가 부족하다.",
            ),
        ],
    )
    exam.id = EXAM_ID
    await ExamSQLAlchemyRepository().save(exam)
    return classroom


@pytest.mark.asyncio
async def test_start_exam_session_persists_result_after_session_row(
    db_session,
):
    classroom = await seed_exam_context(db_session)
    await db_session.commit()
    realtime_port = FakeRealtimeSessionPort()
    service = ExamService(
        repository=ExamSQLAlchemyRepository(),
        classroom_usecase=FakeClassroomUseCase(classroom),
        session_repository=ExamSessionSQLAlchemyRepository(),
        result_repository=ExamResultSQLAlchemyRepository(),
        turn_repository=ExamTurnSQLAlchemyRepository(),
        realtime_session_port=realtime_port,
    )

    result = await service.start_exam_session(
        exam_id=EXAM_ID,
        current_user=make_current_user(),
    )

    session_row = (
        (
            await db_session.execute(
                select(exam_session_table).where(
                    exam_session_table.c.id == result.session.id,
                )
            )
        )
        .mappings()
        .one()
    )
    result_row = (
        (
            await db_session.execute(
                select(exam_result_table).where(
                    exam_result_table.c.session_id == result.session.id,
                )
            )
        )
        .mappings()
        .one()
    )

    assert session_row["id"] == result.session.id
    assert result_row["session_id"] == result.session.id
    assert result_row["exam_id"] == EXAM_ID
    assert result_row["student_id"] == STUDENT_ID
    assert result_row["status"] == ExamResultStatus.PENDING.value
    assert len(realtime_port.calls) == 1
    assert result.client_secret == "ek_test_secret"
    assert result.session.provider_session_id == "sess_test_123"
