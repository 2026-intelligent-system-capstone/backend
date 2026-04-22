from abc import abstractmethod
from collections.abc import AsyncIterator, Sequence
from contextlib import asynccontextmanager
from datetime import datetime
from uuid import UUID

from app.async_job.domain.entity import AsyncJob
from core.repository.base import BaseRepository


class AsyncJobRepository(BaseRepository[AsyncJob]):
    @abstractmethod
    @asynccontextmanager
    async def dedupe_key_lock(
        self,
        *,
        dedupe_key: str,
    ) -> AsyncIterator[None]:
        yield

    @abstractmethod
    async def get_latest_by_target(
        self,
        *,
        target_id: UUID,
    ) -> AsyncJob | None:
        pass

    @abstractmethod
    async def get_active_by_dedupe_key(
        self,
        *,
        dedupe_key: str,
    ) -> AsyncJob | None:
        pass

    @abstractmethod
    async def claim_next_runnable(
        self,
        *,
        now: datetime,
    ) -> AsyncJob | None:
        pass

    @abstractmethod
    async def list_by_target(
        self,
        *,
        target_id: UUID,
    ) -> Sequence[AsyncJob]:
        pass
