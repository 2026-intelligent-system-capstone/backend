import uuid
from contextvars import ContextVar
from uuid import UUID

import pytest
import pytest_asyncio
from sqlalchemy import delete, text
from sqlalchemy.sql.sqltypes import Enum as SQLAlchemyEnum
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_scoped_session,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import NullPool

import app.user.adapter.output.persistence.sqlalchemy.user as user_repo
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
from app.user.adapter.output.persistence.sqlalchemy import (
    UserSQLAlchemyRepository,
)
from app.user.domain.entity import User, UserRole, UserStatus
from core.config import config
from core.db.sqlalchemy import init_orm_mappers
from core.db.sqlalchemy.models.organization import organization_table
from core.db.sqlalchemy.models.user import user_table

try:
    init_orm_mappers()
except Exception:
    pass

ORGANIZATION_ID = UUID("11111111-1111-1111-1111-111111111111")


def assert_enum_column(column, enum_class):
    assert isinstance(column.type, SQLAlchemyEnum)
    assert column.type.enum_class is enum_class
    assert column.type.native_enum is False
    assert column.type.validate_strings is True
    assert column.type.enums == [
        member.value for member in enum_class
    ]


@pytest_asyncio.fixture(autouse=True)
async def setup_db():
    engine = create_async_engine(config.DATABASE_URL, poolclass=NullPool)
    async with engine.begin() as conn:
        await conn.execute(text("DROP TABLE IF EXISTS t_user CASCADE"))
        await conn.execute(text("DROP TABLE IF EXISTS t_organization CASCADE"))
        await conn.run_sync(organization_table.create)
        await conn.run_sync(user_table.create)
    yield
    async with engine.begin() as conn:
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
    organization_repo.session = scoped_session
    user_repo.session = scoped_session

    token = session_context.set(str(uuid.uuid4()))
    async with scoped_session() as s:
        await s.execute(delete(user_table))
        await s.execute(delete(organization_table))
        await s.commit()
        yield s
        await s.execute(delete(user_table))
        await s.execute(delete(organization_table))
        await s.commit()
    await scoped_session.remove()
    await engine.dispose()
    session_context.reset(token)


@pytest.mark.asyncio
async def test_save_and_get_user(db_session):
    organization_adapter = OrganizationSQLAlchemyRepository()
    organization = Organization(
        code="univ_hansung",
        name="한성대학교",
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
        name="리포테스트",
    )
    await adapter.save(user)
    await db_session.commit()

    fetched_user = await adapter.get_by_organization_and_login_id(
        ORGANIZATION_ID,
        "20260001",
    )

    assert fetched_user is not None
    assert fetched_user.login_id == "20260001"
    assert fetched_user.name == "리포테스트"


@pytest.mark.asyncio
async def test_get_by_id_excludes_deleted_user(db_session):
    organization_adapter = OrganizationSQLAlchemyRepository()
    organization = Organization(
        code="univ_hansung",
        name="한성대학교",
        auth_provider=OrganizationAuthProvider.HANSUNG_SIS,
    )
    organization.id = ORGANIZATION_ID
    await organization_adapter.save(organization)

    adapter = UserSQLAlchemyRepository()
    user = User(
        organization_id=ORGANIZATION_ID,
        login_id="20260002",
        role=UserRole.STUDENT,
        email="deleted@example.com",
        name="삭제사용자",
        status=UserStatus.ACTIVE,
        is_deleted=True,
    )

    await adapter.save(user)
    await db_session.commit()

    fetched_user = await adapter.get_by_id(user.id)

    assert fetched_user is None


@pytest.mark.asyncio
async def test_list_excludes_deleted_users(db_session):
    organization_adapter = OrganizationSQLAlchemyRepository()
    organization = Organization(
        code="univ_hansung",
        name="한성대학교",
        auth_provider=OrganizationAuthProvider.HANSUNG_SIS,
    )
    organization.id = ORGANIZATION_ID
    await organization_adapter.save(organization)

    adapter = UserSQLAlchemyRepository()
    active_user = User(
        organization_id=ORGANIZATION_ID,
        login_id="20260003",
        role=UserRole.STUDENT,
        email="active@example.com",
        name="활성사용자",
    )
    active_user.id = UUID("33333333-3333-3333-3333-333333333333")
    deleted_user = User(
        organization_id=ORGANIZATION_ID,
        login_id="20260004",
        role=UserRole.STUDENT,
        email="deleted@example.com",
        name="삭제사용자",
        is_deleted=True,
    )
    deleted_user.id = UUID("44444444-4444-4444-4444-444444444444")

    await adapter.save(active_user)
    await adapter.save(deleted_user)
    await db_session.commit()

    users = await adapter.list()

    assert [user.login_id for user in users] == ["20260003"]


@pytest.mark.asyncio
async def test_list_by_organization_filters_other_organizations(db_session):
    organization_adapter = OrganizationSQLAlchemyRepository()
    primary = Organization(
        code="univ_hansung",
        name="한성대학교",
        auth_provider=OrganizationAuthProvider.HANSUNG_SIS,
    )
    primary.id = ORGANIZATION_ID
    other_organization_id = UUID("22222222-2222-2222-2222-222222222222")
    secondary = Organization(
        code="univ_other",
        name="다른대학교",
        auth_provider=OrganizationAuthProvider.HANSUNG_SIS,
    )
    secondary.id = other_organization_id

    await organization_adapter.save(primary)
    await organization_adapter.save(secondary)

    adapter = UserSQLAlchemyRepository()
    primary_user = User(
        organization_id=ORGANIZATION_ID,
        login_id="20260005",
        role=UserRole.STUDENT,
        email="primary@example.com",
        name="주조직사용자",
    )
    primary_user.id = UUID("55555555-5555-5555-5555-555555555555")
    secondary_user = User(
        organization_id=other_organization_id,
        login_id="20260006",
        role=UserRole.STUDENT,
        email="secondary@example.com",
        name="타조직사용자",
    )
    secondary_user.id = UUID("66666666-6666-6666-6666-666666666666")

    await adapter.save(primary_user)
    await adapter.save(secondary_user)
    await db_session.commit()

    users = await adapter.list_by_organization(ORGANIZATION_ID)

    assert [user.login_id for user in users] == ["20260005"]


def test_user_table_uses_non_native_enum_values():
    assert_enum_column(user_table.c.role, UserRole)
    assert_enum_column(user_table.c.status, UserStatus)
