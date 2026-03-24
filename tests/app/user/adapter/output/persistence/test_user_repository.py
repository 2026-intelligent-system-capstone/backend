import uuid

import pytest
import pytest_asyncio
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import create_async_engine

from app.user.adapter.output.persistence.sqlalchemy.user import (
    UserSQLAlchemyRepository,
)
from app.user.domain.entity.user import Profile, User
from core.config import config
from core.db.session import session, session_context
from core.db.sqlalchemy import init_orm_mappers
from core.db.sqlalchemy.models.base import metadata
from core.db.sqlalchemy.models.user import user_table

try:
    init_orm_mappers()
except Exception:
    pass


@pytest_asyncio.fixture(scope="session", autouse=True)
async def setup_db():
    engine = create_async_engine(config.DATABASE_URL)
    async with engine.begin() as conn:
        await conn.run_sync(metadata.create_all)
    yield
    async with engine.begin() as conn:
        await conn.execute(delete(user_table))
    await engine.dispose()


@pytest_asyncio.fixture
async def db_session():
    token = session_context.set(str(uuid.uuid4()))
    async with session() as s:
        await s.execute(delete(user_table))
        await s.commit()
        yield s
        await s.execute(delete(user_table))
        await s.commit()
    await session.remove()
    session_context.reset(token)


@pytest.mark.asyncio
async def test_save_and_get_user(db_session):
    adapter = UserSQLAlchemyRepository()
    profile = Profile(nickname="repo_test", real_name="리포테스트")
    user = User(
        username="repo_user",
        password="hashed_password",
        email="repo@example.com",
        profile=profile,
    )
    await adapter.save(user)
    await db_session.commit()

    fetched_user = await adapter.get_by_email("repo@example.com")

    assert fetched_user is not None
    assert fetched_user.username == "repo_user"
    assert fetched_user.profile.nickname == "repo_test"
