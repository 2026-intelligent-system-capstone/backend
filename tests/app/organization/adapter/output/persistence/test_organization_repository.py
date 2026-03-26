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
from core.db.sqlalchemy.models.organization import organization_table

try:
    init_orm_mappers()
except Exception:
    pass

ORGANIZATION_ID = UUID("11111111-1111-1111-1111-111111111111")


@pytest_asyncio.fixture(autouse=True)
async def setup_db():
    engine = create_async_engine(config.DATABASE_URL, poolclass=NullPool)
    async with engine.begin() as conn:
        await conn.run_sync(metadata.create_all)
    yield
    async with engine.begin() as conn:
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

    token = session_context.set(str(uuid.uuid4()))
    async with scoped_session() as s:
        await s.execute(delete(organization_table))
        await s.commit()
        yield s
        await s.execute(delete(organization_table))
        await s.commit()
    await scoped_session.remove()
    await engine.dispose()
    session_context.reset(token)


@pytest.mark.asyncio
async def test_save_and_get_organization(db_session):
    adapter = OrganizationSQLAlchemyRepository()
    organization = Organization(
        code="univ_hansung",
        name="한성대학교",
        auth_provider=OrganizationAuthProvider.HANSUNG_SIS,
    )
    organization.id = ORGANIZATION_ID

    await adapter.save(organization)
    await db_session.commit()

    fetched_organization = await adapter.get_by_code("univ_hansung")

    assert fetched_organization is not None
    assert fetched_organization.name == "한성대학교"


@pytest.mark.asyncio
async def test_get_by_id_returns_organization(db_session):
    adapter = OrganizationSQLAlchemyRepository()
    organization = Organization(
        code="univ_hansung",
        name="한성대학교",
        auth_provider=OrganizationAuthProvider.HANSUNG_SIS,
    )
    organization.id = ORGANIZATION_ID

    await adapter.save(organization)
    await db_session.commit()

    fetched_organization = await adapter.get_by_id(ORGANIZATION_ID)

    assert fetched_organization is not None
    assert fetched_organization.id == ORGANIZATION_ID


@pytest.mark.asyncio
async def test_list_returns_organizations_sorted_by_name(db_session):
    adapter = OrganizationSQLAlchemyRepository()
    zeta = Organization(
        code="univ_zeta",
        name="제타대학교",
        auth_provider=OrganizationAuthProvider.HANSUNG_SIS,
    )
    zeta.id = UUID("22222222-2222-2222-2222-222222222222")
    alpha = Organization(
        code="univ_alpha",
        name="알파대학교",
        auth_provider=OrganizationAuthProvider.HANSUNG_SIS,
    )
    alpha.id = UUID("33333333-3333-3333-3333-333333333333")

    await adapter.save(zeta)
    await adapter.save(alpha)
    await db_session.commit()

    organizations = await adapter.list()

    assert [organization.name for organization in organizations] == [
        "알파대학교",
        "제타대학교",
    ]
