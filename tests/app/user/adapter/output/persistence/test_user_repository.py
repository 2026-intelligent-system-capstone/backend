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
from app.user.adapter.output.persistence.sqlalchemy.user import (
    UserSQLAlchemyRepository,
)
from app.user.domain.entity.user import Profile, User, UserRole
from core.config import config
from core.db.session import session, session_context
from core.db.sqlalchemy import init_orm_mappers
from core.db.sqlalchemy.models.base import metadata
from core.db.sqlalchemy.models.organization import organization_table
from core.db.sqlalchemy.models.user import user_table

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
        await conn.execute(delete(user_table))
        await conn.execute(delete(organization_table))
    await engine.dispose()


@pytest_asyncio.fixture
async def db_session():
    token = session_context.set(str(uuid.uuid4()))
    async with session() as s:
        await s.execute(delete(user_table))
        await s.execute(delete(organization_table))
        await s.commit()
        yield s
        await s.execute(delete(user_table))
        await s.execute(delete(organization_table))
        await s.commit()
    await session.remove()
    session_context.reset(token)


@pytest.mark.asyncio
async def test_save_and_get_user(db_session):
    organization_adapter = OrganizationSQLAlchemyRepository()
    organization = Organization(
        code="hansung",
        name="Hansung University",
        auth_provider=OrganizationAuthProvider.HANSUNG_SIS,
    )
    organization.id = ORGANIZATION_ID
    await organization_adapter.save(organization)

    adapter = UserSQLAlchemyRepository()
    user = User(
        organization_id=ORGANIZATION_ID,
        login_id="20260001",
        role=UserRole.STUDENT,
        email="repo@example.com",
        profile=Profile(nickname="repo_test", name="리포테스트"),
    )
    await adapter.save(user)
    await db_session.commit()

    fetched_user = await adapter.get_by_organization_and_login_id(
        ORGANIZATION_ID,
        "20260001",
    )

    assert fetched_user is not None
    assert fetched_user.login_id == "20260001"
    assert fetched_user.profile.nickname == "repo_test"
