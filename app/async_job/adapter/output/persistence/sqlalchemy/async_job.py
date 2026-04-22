from collections.abc import AsyncIterator, Sequence
from contextlib import asynccontextmanager
from datetime import datetime
from uuid import UUID

from app.async_job.domain.entity import AsyncJob, AsyncJobStatus
from app.async_job.domain.repository import AsyncJobRepository
from core.db.session import session
from core.db.sqlalchemy.models.async_job import async_job_table
from sqlalchemy import select, text

ADVISORY_LOCK_SQL = "SELECT pg_advisory_xact_lock(hashtext(:lock_key))"


class AsyncJobSQLAlchemyRepository(AsyncJobRepository):
    @asynccontextmanager
    async def dedupe_key_lock(
        self,
        *,
        dedupe_key: str,
    ) -> AsyncIterator[None]:
        await session.execute(
            text(ADVISORY_LOCK_SQL),
            {
                "lock_key": f"async-job-dedupe:{dedupe_key}",
            },
        )
        yield

    async def save(self, entity: AsyncJob) -> None:
        session.add(entity)

    async def get_by_id(self, entity_id: UUID) -> AsyncJob | None:
        query = select(AsyncJob).where(async_job_table.c.id == entity_id)
        result = await session.execute(query)
        return result.scalar_one_or_none()

    async def list(self) -> Sequence[AsyncJob]:
        query = select(AsyncJob).order_by(async_job_table.c.created_at.desc())
        result = await session.execute(query)
        return list(result.scalars().all())

    async def get_latest_by_target(
        self,
        *,
        target_id: UUID,
    ) -> AsyncJob | None:
        query = (
            select(AsyncJob)
            .where(async_job_table.c.target_id == target_id)
            .order_by(async_job_table.c.created_at.desc())
            .limit(1)
        )
        result = await session.execute(query)
        return result.scalar_one_or_none()

    async def list_by_target(
        self,
        *,
        target_id: UUID,
    ) -> Sequence[AsyncJob]:
        query = (
            select(AsyncJob)
            .where(async_job_table.c.target_id == target_id)
            .order_by(async_job_table.c.created_at.desc())
        )
        result = await session.execute(query)
        return list(result.scalars().all())

    async def get_active_by_dedupe_key(
        self,
        *,
        dedupe_key: str,
    ) -> AsyncJob | None:
        query = (
            select(AsyncJob)
            .where(
                async_job_table.c.dedupe_key == dedupe_key,
                async_job_table.c.status.in_((
                    AsyncJobStatus.QUEUED.value,
                    AsyncJobStatus.RUNNING.value,
                )),
            )
            .order_by(async_job_table.c.created_at.desc())
            .limit(1)
        )
        result = await session.execute(query)
        return result.scalar_one_or_none()

    async def claim_next_runnable(
        self,
        *,
        now: datetime,
    ) -> AsyncJob | None:
        query = (
            select(AsyncJob)
            .where(
                async_job_table.c.status == AsyncJobStatus.QUEUED.value,
                async_job_table.c.available_at <= now,
            )
            .order_by(async_job_table.c.available_at.asc())
            .limit(1)
            .with_for_update(skip_locked=True)
        )
        result = await session.execute(query)
        return result.scalar_one_or_none()
