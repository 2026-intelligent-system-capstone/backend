import uuid
from contextvars import ContextVar
from uuid import UUID

import pytest
import pytest_asyncio
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_scoped_session,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import NullPool

from app.classroom.adapter.output.persistence.sqlalchemy import (
    classroom as classroom_repo,
)
from app.classroom.adapter.output.persistence.sqlalchemy.classroom import (
    ClassroomSQLAlchemyRepository,
)
from app.classroom.domain.entity import Classroom
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
from core.config import config
from core.db.sqlalchemy import init_orm_mappers
from core.db.sqlalchemy.models.base import metadata
from core.db.sqlalchemy.models.classroom import classroom_table
from core.db.sqlalchemy.models.organization import organization_table

try:
    init_orm_mappers()
except Exception:
    pass

ORGANIZATION_ID = UUID("11111111-1111-1111-1111-111111111111")
OTHER_ORGANIZATION_ID = UUID("22222222-2222-2222-2222-222222222222")
CLASSROOM_ID = UUID("33333333-3333-3333-3333-333333333333")


@pytest_asyncio.fixture(autouse=True)
async def setup_db():
    engine = create_async_engine(config.DATABASE_URL, poolclass=NullPool)
    async with engine.begin() as conn:
        await conn.run_sync(metadata.create_all)
    yield
    async with engine.begin() as conn:
        await conn.execute(delete(classroom_table))
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
    organization_repo.session = scoped_session
    classroom_repo.session = scoped_session

    token = session_context.set(str(uuid.uuid4()))
    async with scoped_session() as current_session:
        await current_session.execute(delete(classroom_table))
        await current_session.execute(delete(organization_table))
        await current_session.commit()
        yield current_session
        await current_session.execute(delete(classroom_table))
        await current_session.execute(delete(organization_table))
        await current_session.commit()
    await scoped_session.remove()
    await engine.dispose()
    session_context.reset(token)


async def save_organizations() -> None:
    adapter = OrganizationSQLAlchemyRepository()

    organization = Organization(
        code="univ_hansung",
        name="한성대학교",
        auth_provider=OrganizationAuthProvider.HANSUNG_SIS,
    )
    organization.id = ORGANIZATION_ID

    other_organization = Organization(
        code="univ_other",
        name="다른대학교",
        auth_provider=OrganizationAuthProvider.HANSUNG_SIS,
    )
    other_organization.id = OTHER_ORGANIZATION_ID

    await adapter.save(organization)
    await adapter.save(other_organization)


def make_classroom(
    *,
    organization_id: UUID = ORGANIZATION_ID,
    name: str = "알고리즘",
    grade: int = 1,
    semester: str = "1",
    section: str = "01",
) -> Classroom:
    classroom = Classroom(
        organization_id=organization_id,
        name=name,
        professor_ids=[UUID("44444444-4444-4444-4444-444444444444")],
        grade=grade,
        semester=semester,
        section=section,
        description="자료구조와 알고리즘",
        student_ids=[UUID("55555555-5555-5555-5555-555555555555")],
    )
    return classroom


@pytest.mark.asyncio
async def test_save_and_get_classroom(db_session):
    await save_organizations()
    await db_session.commit()
    adapter = ClassroomSQLAlchemyRepository()
    classroom = make_classroom()
    classroom.id = CLASSROOM_ID

    await adapter.save(classroom)
    await db_session.commit()

    fetched_classroom = await adapter.get_by_id(CLASSROOM_ID)

    assert fetched_classroom is not None
    assert fetched_classroom.id == CLASSROOM_ID
    assert fetched_classroom.name == "알고리즘"


@pytest.mark.asyncio
async def test_list_by_organization_returns_only_matching_classrooms(
    db_session,
):
    await save_organizations()
    await db_session.commit()
    adapter = ClassroomSQLAlchemyRepository()
    primary = make_classroom(name="알고리즘")
    primary.id = CLASSROOM_ID
    other = make_classroom(
        organization_id=OTHER_ORGANIZATION_ID,
        name="운영체제",
    )
    other.id = UUID("44444444-4444-4444-4444-444444444444")

    await adapter.save(primary)
    await adapter.save(other)
    await db_session.commit()

    classrooms = await adapter.list_by_organization(ORGANIZATION_ID)

    assert [classroom.name for classroom in classrooms] == ["알고리즘"]


@pytest.mark.asyncio
async def test_get_by_organization_and_name_and_term_returns_match(db_session):
    await save_organizations()
    await db_session.commit()
    adapter = ClassroomSQLAlchemyRepository()
    classroom = make_classroom(name="운영체제", grade=2, section="02")
    classroom.id = CLASSROOM_ID

    await adapter.save(classroom)
    await db_session.commit()

    fetched_classroom = await adapter.get_by_organization_and_name_and_term(
        ORGANIZATION_ID,
        "운영체제",
        2,
        "1",
        "02",
    )

    assert fetched_classroom is not None
    assert fetched_classroom.name == "운영체제"
