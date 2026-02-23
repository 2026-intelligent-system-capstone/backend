import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from app.user.adapter.output.persistence.repository import UserPersistenceAdapter
from app.user.domain.entity.user import User, Profile
from core.db.mixins import Base
from core.db.session import session, session_context
from core.config import config
import uuid

@pytest_asyncio.fixture(scope="session", autouse=True)
async def setup_db():
    # Use the test database configured in CI or local .env
    engine = create_async_engine(config.DATABASE_URL)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()

@pytest_asyncio.fixture
async def db_session():
    token = session_context.set(str(uuid.uuid4()))
    async with session() as s:
        yield s
    await session.remove()
    session_context.reset(token)

@pytest.mark.asyncio
async def test_save_and_get_user(db_session):
    # Given
    adapter = UserPersistenceAdapter()
    profile = Profile(nickname="repo_test", real_name="리포테스트")
    user = User(
        username="repo_user",
        password="hashed_password",
        email="repo@example.com",
        profile=profile
    )

    # When
    saved_user = await adapter.save(user)
    await db_session.commit()
    
    fetched_user = await adapter.get_by_email("repo@example.com")

    # Then
    assert fetched_user is not None
    assert fetched_user.id == saved_user.id
    assert fetched_user.username == "repo_user"
    assert fetched_user.profile.nickname == "repo_test"

@pytest.mark.asyncio
async def test_get_non_existent_user(db_session):
    # Given
    adapter = UserPersistenceAdapter()

    # When
    fetched_user = await adapter.get_by_email("none@example.com")

    # Then
    assert fetched_user is None
