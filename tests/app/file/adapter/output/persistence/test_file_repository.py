import uuid
from contextvars import ContextVar
from uuid import UUID

import pytest
import pytest_asyncio
from sqlalchemy import delete, text
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_scoped_session,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import NullPool
from sqlalchemy.sql.sqltypes import Enum as SQLAlchemyEnum

from app.file.adapter.output.persistence.sqlalchemy import file as file_repo
from app.file.adapter.output.persistence.sqlalchemy.file import (
    FileSQLAlchemyRepository,
)
from app.file.domain.entity.file import File, FileStatus
from core.config import config
from core.db.sqlalchemy import init_orm_mappers
from core.db.sqlalchemy.models.file import file_table

try:
    init_orm_mappers()
except Exception:
    pass

FILE_ID = UUID("11111111-1111-1111-1111-111111111111")
DELETED_FILE_ID = UUID("22222222-2222-2222-2222-222222222222")


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
        await conn.execute(text("DROP TABLE IF EXISTS t_file CASCADE"))
        await conn.run_sync(file_table.create)
    yield
    async with engine.begin() as conn:
        await conn.execute(delete(file_table))
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
    file_repo.session = scoped_session

    token = session_context.set(str(uuid.uuid4()))
    async with scoped_session() as current_session:
        await current_session.execute(delete(file_table))
        await current_session.commit()
        yield current_session
        await current_session.execute(delete(file_table))
        await current_session.commit()
    await scoped_session.remove()
    await engine.dispose()
    session_context.reset(token)


def make_file(*, status: FileStatus = FileStatus.PENDING) -> File:
    file = File(
        file_name="week1.pdf",
        file_path="classrooms/week1.pdf",
        file_extension="pdf",
        file_size=1024,
        mime_type="application/pdf",
        status=status,
    )
    return file


@pytest.mark.asyncio
async def test_save_and_get_file(db_session):
    adapter = FileSQLAlchemyRepository()
    file = make_file(status=FileStatus.ACTIVE)
    file.id = FILE_ID

    await adapter.save(file)
    await db_session.commit()

    fetched_file = await adapter.get_by_id(FILE_ID)

    assert fetched_file is not None
    assert fetched_file.id == FILE_ID
    assert fetched_file.file_name == "week1.pdf"
    assert fetched_file.status == FileStatus.ACTIVE


@pytest.mark.asyncio
async def test_list_excludes_deleted_files(db_session):
    adapter = FileSQLAlchemyRepository()
    active_file = make_file(status=FileStatus.ACTIVE)
    active_file.id = FILE_ID
    deleted_file = make_file(status=FileStatus.DELETED)
    deleted_file.id = DELETED_FILE_ID

    await adapter.save(active_file)
    await adapter.save(deleted_file)
    await db_session.commit()

    files = await adapter.list()

    assert [file.id for file in files] == [FILE_ID]


def test_file_table_uses_non_native_enum_values():
    assert_enum_column(file_table.c.status, FileStatus)
