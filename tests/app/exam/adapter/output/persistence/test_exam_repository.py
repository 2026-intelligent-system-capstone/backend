import uuid
from contextvars import ContextVar
from datetime import UTC, datetime, timedelta
from uuid import UUID

import pytest
import pytest_asyncio
from sqlalchemy import delete, make_url, text
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_scoped_session,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.sql.sqltypes import Enum as SQLAlchemyEnum

import core.db.sqlalchemy as sqlalchemy_mapping
from app.classroom.adapter.output.persistence.sqlalchemy import (
    classroom as classroom_repo,
)
from app.classroom.adapter.output.persistence.sqlalchemy.classroom import (
    ClassroomSQLAlchemyRepository,
)
from app.classroom.domain.entity import Classroom
from app.exam.adapter.output.persistence.sqlalchemy import exam as exam_repo
from app.exam.adapter.output.persistence.sqlalchemy.exam import (
    ExamSQLAlchemyRepository,
)
from app.exam.domain.entity import (
    BloomLevel,
    Exam,
    ExamDifficulty,
    ExamQuestion,
    ExamQuestionStatus,
    ExamQuestionType,
    ExamResultStatus,
    ExamSessionStatus,
    ExamStatus,
    ExamTurnEventType,
    ExamTurnRole,
    ExamType,
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
from core.db.sqlalchemy.models.classroom import classroom_table
from core.db.sqlalchemy.models.exam import (
    exam_criterion_table,
    exam_question_table,
    exam_result_criterion_table,
    exam_result_table,
    exam_session_table,
    exam_table,
    exam_turn_table,
)
from core.db.sqlalchemy.models.organization import organization_table
from core.db.sqlalchemy.models.user import user_table

sqlalchemy_mapping.init_orm_mappers()

ORG_ID = UUID("11111111-1111-1111-1111-111111111111")
CLASSROOM_ID = UUID("22222222-2222-2222-2222-222222222222")
PROFESSOR_ID = UUID("44444444-4444-4444-4444-444444444444")
NOW = datetime.now(UTC)
STARTS_AT = NOW - timedelta(minutes=5)
ENDS_AT = NOW + timedelta(hours=1)


def assert_test_database_url(database_url: str) -> None:
    database_name = make_url(database_url).database or ""
    if "test" not in database_name.lower():
        raise RuntimeError("repository tests require a test database")


def test_repository_fixture_rejects_non_test_database_url():
    with pytest.raises(RuntimeError, match="test database"):
        assert_test_database_url(
            "postgresql+asyncpg://postgres:password@127.0.0.1:55432/dialearn"
        )


@pytest_asyncio.fixture(autouse=True)
async def setup_db():
    assert_test_database_url(config.DATABASE_URL)
    engine = create_async_engine(config.DATABASE_URL)
    async with engine.begin() as conn:
        await conn.run_sync(metadata_drop_exam_repository_tables)
        await conn.run_sync(organization_table.create)
        await conn.run_sync(user_table.create)
        await conn.run_sync(classroom_table.create)
        await conn.run_sync(exam_table.create)
        await conn.run_sync(exam_criterion_table.create)
        await conn.run_sync(exam_question_table.create)
    yield
    async with engine.begin() as conn:
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

    engine = create_async_engine(config.DATABASE_URL)
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
    )
    organization_repo.session = scoped_session
    user_repo.session = scoped_session
    classroom_repo.session = scoped_session
    exam_repo.session = scoped_session

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
        ) = original_sessions
        await scoped_session.remove()
        await engine.dispose()
        session_context.reset(token)


def metadata_drop_exam_repository_tables(connection):
    for table_name in (
        "t_exam_turn",
        "t_exam_result_criterion",
        "t_exam_result",
        "t_exam_session",
        "t_exam_question",
        "t_exam_criterion",
        "t_exam",
        "t_classroom",
        "t_user",
        "t_organization",
    ):
        connection.execute(text(f"DROP TABLE IF EXISTS {table_name} CASCADE"))


async def seed_exam_context(db_session: AsyncSession) -> None:
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
    await UserSQLAlchemyRepository().save(professor)
    await db_session.flush()

    classroom = Classroom(
        organization_id=ORG_ID,
        name="AI 기초",
        professor_ids=[PROFESSOR_ID],
        grade=4,
        semester="1",
        section="01",
        description="캡스톤 시험 수업",
        student_ids=[],
    )
    classroom.id = CLASSROOM_ID
    await ClassroomSQLAlchemyRepository().save(classroom)
    await db_session.flush()


def make_exam(
    *,
    question_count: int,
    difficulty: ExamDifficulty,
) -> Exam:
    return Exam.create(
        classroom_id=CLASSROOM_ID,
        title="중간 평가",
        description="1주차 범위 평가",
        exam_type=ExamType.MIDTERM,
        duration_minutes=60,
        starts_at=STARTS_AT,
        ends_at=ENDS_AT,
        max_attempts=1,
        week=1,
        criteria=[],
        question_count=question_count,
        difficulty=difficulty,
    )


def assert_enum_column(column, enum_class):
    assert isinstance(column.type, SQLAlchemyEnum)
    assert column.type.enum_class is enum_class
    assert column.type.native_enum is False
    assert column.type.validate_strings is True
    assert column.type.enums == [member.value for member in enum_class]


@pytest.mark.asyncio
async def test_exam_repository_round_trips_question_count_and_difficulty(
    db_session,
):
    await seed_exam_context(db_session)
    exam = make_exam(question_count=12, difficulty=ExamDifficulty.HARD)

    await ExamSQLAlchemyRepository().save(exam)
    await db_session.commit()
    db_session.expunge_all()
    loaded = await ExamSQLAlchemyRepository().get_by_id(exam.id)

    assert loaded is not None
    assert loaded.question_count == 12
    assert loaded.difficulty is ExamDifficulty.HARD


def test_exam_table_uses_sqlalchemy_enum_columns():
    assert_enum_column(exam_table.c.exam_type, ExamType)
    assert_enum_column(exam_table.c.status, ExamStatus)
    assert_enum_column(exam_table.c.difficulty, ExamDifficulty)


def test_exam_table_contains_non_nullable_week_column():
    assert exam_table.c.week.nullable is False


def test_exam_table_contains_non_nullable_max_attempts_column():
    assert exam_table.c.max_attempts.nullable is False
    assert exam_table.c.max_attempts.default is not None
    assert exam_table.c.max_attempts.default.arg == 1


def test_exam_table_contains_question_count_column_and_range_constraint():
    assert exam_table.c.question_count.nullable is False
    assert exam_table.c.question_count.default is not None
    assert exam_table.c.question_count.default.arg == 1
    check_constraints = [
        constraint
        for constraint in exam_table.constraints
        if constraint.__class__.__name__ == "CheckConstraint"
    ]

    assert any(
        constraint.name == "ck_t_exam_question_count_range"
        and str(constraint.sqltext) == "question_count BETWEEN 1 AND 30"
        for constraint in check_constraints
    )


def test_exam_question_table_uses_sqlalchemy_enum_columns():
    assert_enum_column(exam_question_table.c.question_type, ExamQuestionType)
    assert_enum_column(exam_question_table.c.bloom_level, BloomLevel)
    assert_enum_column(exam_question_table.c.difficulty, ExamDifficulty)
    assert_enum_column(exam_question_table.c.status, ExamQuestionStatus)


def test_exam_question_table_contains_merged_intent_and_rubric_columns():
    assert exam_question_table.c.intent_text.nullable is False
    assert exam_question_table.c.intent_text.type.length == 5000
    assert exam_question_table.c.rubric_text.nullable is False
    assert exam_question_table.c.rubric_text.type.length == 12000
    assert exam_question_table.c.answer_options.nullable is False
    assert exam_question_table.c.correct_answer_text.nullable is True
    assert exam_question_table.c.correct_answer_text.type.length == 2000


def test_exam_question_table_keeps_legacy_columns_for_backfill_compatibility():
    assert exam_question_table.c.scope_text.nullable is True
    assert exam_question_table.c.evaluation_objective.nullable is True
    assert exam_question_table.c.answer_key.nullable is True
    assert exam_question_table.c.scoring_criteria.nullable is True


def test_exam_question_table_contains_non_nullable_max_score_column():
    assert exam_question_table.c.max_score.nullable is False
    assert exam_question_table.c.max_score.default is not None
    assert exam_question_table.c.max_score.default.arg == 1.0


def test_exam_question_table_contains_positive_max_score_check_constraint():
    check_constraints = [
        constraint
        for constraint in exam_question_table.constraints
        if constraint.__class__.__name__ == "CheckConstraint"
    ]

    assert any(
        constraint.name == "ck_t_exam_question_max_score_positive"
        and str(constraint.sqltext) == "max_score > 0"
        for constraint in check_constraints
    )


def test_legacy_multiple_choice_question_without_options_still_loads():
    question = ExamQuestion(
        exam_id=UUID("11111111-1111-1111-1111-111111111111"),
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

    assert question.question_type is ExamQuestionType.MULTIPLE_CHOICE
    assert question.answer_options == []
    assert question.correct_answer_text == "회귀"


def test_exam_question_table_serializes_source_material_ids_as_json_strings():
    source_material_ids = exam_question_table.c.source_material_ids
    bind_param = source_material_ids.type.process_bind_param
    bind_value = bind_param(
        [
            UUID("99999999-9999-9999-9999-999999999999"),
            UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"),
        ],
        None,
    )

    assert bind_value == [
        "99999999-9999-9999-9999-999999999999",
        "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
    ]


def test_exam_question_table_restores_source_material_ids_as_uuid_list():
    source_material_ids = exam_question_table.c.source_material_ids
    process_result = source_material_ids.type.process_result_value
    result_value = process_result(
        [
            "99999999-9999-9999-9999-999999999999",
            "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
        ],
        None,
    )

    assert result_value == [
        UUID("99999999-9999-9999-9999-999999999999"),
        UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"),
    ]


def test_exam_question_table_rejects_null_source_material_ids_on_bind():
    source_material_ids = exam_question_table.c.source_material_ids
    bind_param = source_material_ids.type.process_bind_param

    with pytest.raises(TypeError, match="source_material_ids cannot be null"):
        bind_param(None, None)


def test_exam_question_table_rejects_invalid_source_material_id_member():
    source_material_ids = exam_question_table.c.source_material_ids
    bind_param = source_material_ids.type.process_bind_param

    with pytest.raises(
        TypeError,
        match="source_material_ids must contain UUID values",
    ):
        bind_param([123], None)


def test_exam_question_table_rejects_invalid_source_material_id_string():
    source_material_ids = exam_question_table.c.source_material_ids
    process_result = source_material_ids.type.process_result_value

    with pytest.raises(
        ValueError,
        match="badly formed hexadecimal UUID string",
    ):
        process_result(["not-a-uuid"], None)


def test_exam_session_and_result_tables_use_sqlalchemy_enum_columns():
    assert_enum_column(exam_session_table.c.status, ExamSessionStatus)
    assert_enum_column(exam_result_table.c.status, ExamResultStatus)


def test_exam_result_table_contains_rich_feedback_columns():
    assert exam_result_table.c.overall_score.nullable is True
    assert exam_result_table.c.summary.type.length == 2000
    assert exam_result_table.c.strengths.nullable is False
    assert exam_result_table.c.weaknesses.nullable is False
    assert exam_result_table.c.improvement_suggestions.nullable is False


def test_exam_result_criterion_table_contains_score_and_feedback_columns():
    assert exam_result_criterion_table.c.result_id.nullable is False
    assert exam_result_criterion_table.c.criterion_id.nullable is False
    assert exam_result_criterion_table.c.score.nullable is True
    assert exam_result_criterion_table.c.feedback.nullable is True
    assert exam_result_criterion_table.c.feedback.type.length == 2000


def test_exam_session_table_contains_unique_attempt_constraint():
    unique_constraints = list(exam_session_table.constraints)

    assert any(
        constraint.__class__.__name__ == "UniqueConstraint"
        and tuple(constraint.columns.keys())
        == ("exam_id", "student_id", "attempt_number")
        for constraint in unique_constraints
    )


def test_exam_session_table_contains_single_in_progress_index():
    assert any(
        index.name == "ix_t_exam_session_single_in_progress"
        and tuple(column.name for column in index.columns)
        == ("exam_id", "student_id")
        and index.unique is True
        for index in exam_session_table.indexes
    )


def test_exam_turn_table_uses_sqlalchemy_enum_columns():
    assert_enum_column(exam_turn_table.c.role, ExamTurnRole)
    assert_enum_column(exam_turn_table.c.event_type, ExamTurnEventType)
