import asyncio
import logging
from contextlib import asynccontextmanager

from sqlalchemy import inspect

from app.async_job.adapter.output.persistence.sqlalchemy import (
    AsyncJobSQLAlchemyRepository,
)
from app.async_job.application.service import AsyncJobWorker
from app.classroom.adapter.output.integration import (
    LLMClassroomMaterialIngestAdapter,
)
from app.classroom.adapter.output.persistence.sqlalchemy import (
    ClassroomMaterialSQLAlchemyRepository,
    ClassroomSQLAlchemyRepository,
)
from app.exam.adapter.output.integration import (
    LLMExamQuestionGenerationAdapter,
)
from app.exam.adapter.output.persistence.sqlalchemy import (
    ExamResultSQLAlchemyRepository,
    ExamSessionSQLAlchemyRepository,
    ExamSQLAlchemyRepository,
    ExamTurnSQLAlchemyRepository,
)
from core.db.session import engine
from core.db.sqlalchemy.models.async_job import async_job_table
from core.fastapi import ExtendedFastAPI

logger = logging.getLogger(__name__)


async def _async_job_table_exists() -> bool:
    async with engine.begin() as connection:
        return await connection.run_sync(
            lambda sync_connection: bool(
                inspect(sync_connection).has_table(async_job_table.name)
            )
        )


def _validate_poll_interval(interval: float) -> float:
    if interval <= 0:
        raise ValueError(
            "ASYNC_JOB_WORKER_POLL_INTERVAL_SECONDS must be positive"
        )
    return interval


def _build_async_job_worker(app: ExtendedFastAPI) -> AsyncJobWorker:
    return AsyncJobWorker(
        repository=AsyncJobSQLAlchemyRepository(),
        classroom_repository=ClassroomSQLAlchemyRepository(),
        material_repository=ClassroomMaterialSQLAlchemyRepository(),
        file_usecase=app.container.file.service(),
        material_ingest_port=LLMClassroomMaterialIngestAdapter(),
        exam_repository=ExamSQLAlchemyRepository(),
        question_generation_port=LLMExamQuestionGenerationAdapter(),
        exam_session_repository=ExamSessionSQLAlchemyRepository(),
        exam_result_repository=ExamResultSQLAlchemyRepository(),
        exam_turn_repository=ExamTurnSQLAlchemyRepository(),
        result_evaluation_port=app.container.exam.result_evaluation_port(),
    )


async def _run_async_job_worker_once(worker: AsyncJobWorker) -> bool:
    return await worker.run_next_queued_job()


async def _async_job_worker_loop(
    app: ExtendedFastAPI,
    *,
    worker: AsyncJobWorker | None = None,
    interval: float | None = None,
) -> None:
    resolved_worker = worker or _build_async_job_worker(app)
    resolved_interval = (
        _validate_poll_interval(interval)
        if interval is not None
        else _validate_poll_interval(
            app.settings.ASYNC_JOB_WORKER_POLL_INTERVAL_SECONDS
        )
    )

    while True:
        try:
            handled = await _run_async_job_worker_once(resolved_worker)
            if handled:
                continue
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Async job worker loop failed")

        await asyncio.sleep(resolved_interval)


@asynccontextmanager
async def lifespan(app: ExtendedFastAPI):
    worker_task: asyncio.Task[None] | None = None

    if app.settings.ASYNC_JOB_WORKER_ENABLED:
        interval = _validate_poll_interval(
            app.settings.ASYNC_JOB_WORKER_POLL_INTERVAL_SECONDS
        )
        if await _async_job_table_exists():
            worker = _build_async_job_worker(app)
            worker_task = asyncio.create_task(
                _async_job_worker_loop(app, worker=worker, interval=interval)
            )
        else:
            logger.warning(
                "Async job worker disabled because %s table does not exist yet",
                async_job_table.name,
            )

    try:
        yield
    finally:
        if worker_task is not None:
            worker_task.cancel()
            try:
                await worker_task
            except asyncio.CancelledError:
                pass
