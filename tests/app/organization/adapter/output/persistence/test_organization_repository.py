import uuid
from uuid import UUID

import pytest
import pytest_asyncio
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import create_async_engine

from app.organization.adapter.output.persistence.sqlalchemy import (
    OrganizationSQLAlchemyRepository,
)
from app.organization.domain.entity.organization import (
    Organization,
    OrganizationAuthProvider,
)
from core.config import config
from core.db.session import session, session_context
from core.db.sqlalchemy import init_orm_mappers
from core.db.sqlalchemy.models.base import metadata
from core.db.sqlalchemy.models.organization import organization_table

try:
    init_orm_mappers()
except Exception:
    pass

ORGANIZATION_ID = UUID("11111111-1111-1111-1111-111111111111")


@pytest_asyncio.fixture(scope="session", autouse=True)
async def setup_db():
    engine = create_async_engine(config.DATABASE_URL)
    async with engine.begin() as conn:
        await conn.run_sync(metadata.create_all)
    yield
    async with engine.begin() as conn:
        await conn.execute(delete(organization_table))
    await engine.dispose()


@pytest_asyncio.fixture
async def db_session():
    token = session_context.set(str(uuid.uuid4()))
    async with session() as s:
        await s.execute(delete(organization_table))
        await s.commit()
        yield s
        await s.execute(delete(organization_table))
        await s.commit()
    await session.remove()
    session_context.reset(token)


@pytest.mark.asyncio
async def test_save_and_get_organization(db_session):
    adapter = OrganizationSQLAlchemyRepository()
    organization = Organization(
        code="hansung",
        name="Hansung University",
        auth_provider=OrganizationAuthProvider.HANSUNG_SIS,
    )
    organization.id = ORGANIZATION_ID

    await adapter.save(organization)
    await db_session.commit()

    fetched_organization = await adapter.get_by_code("hansung")

    assert fetched_organization is not None
    assert fetched_organization.name == "Hansung University"
