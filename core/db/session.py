from contextvars import ContextVar

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_scoped_session,
    async_sessionmaker,
    create_async_engine,
)

from core.config import config

session_context: ContextVar[str] = ContextVar("session_context", default="global")


def get_session_context() -> str:
    return session_context.get()


engine = create_async_engine(config.DATABASE_URL, pool_pre_ping=True)
async_session_factory = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
)

session = async_scoped_session(
    session_factory=async_session_factory,
    scopefunc=get_session_context,
)
