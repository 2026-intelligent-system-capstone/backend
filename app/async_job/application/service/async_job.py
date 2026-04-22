from uuid import UUID

from app.async_job.domain.entity import (
    AsyncJob,
    AsyncJobTargetType,
    AsyncJobType,
)
from app.async_job.domain.repository import AsyncJobRepository


class AsyncJobService:
    def __init__(self, *, repository: AsyncJobRepository):
        self.repository = repository

    async def enqueue(
        self,
        *,
        job_type: AsyncJobType,
        target_type: AsyncJobTargetType,
        target_id: UUID,
        requested_by: UUID,
        payload: dict[str, object],
        dedupe_key: str | None = None,
    ) -> AsyncJob:
        if dedupe_key is not None:
            async with self.repository.dedupe_key_lock(dedupe_key=dedupe_key):
                existing_job = await self.repository.get_active_by_dedupe_key(dedupe_key=dedupe_key)
                if existing_job is not None:
                    return existing_job

                job = AsyncJob.enqueue(
                    job_type=job_type,
                    target_type=target_type,
                    target_id=target_id,
                    requested_by=requested_by,
                    payload=payload,
                    dedupe_key=dedupe_key,
                )
                await self.repository.save(job)
                return job

        job = AsyncJob.enqueue(
            job_type=job_type,
            target_type=target_type,
            target_id=target_id,
            requested_by=requested_by,
            payload=payload,
            dedupe_key=None,
        )
        await self.repository.save(job)
        return job
