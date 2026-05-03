from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any
from uuid import UUID

from core.common.entity import Entity

ASYNC_JOB_ERROR_MESSAGE_MAX_LENGTH = 1000


class AsyncJobType(StrEnum):
    MATERIAL_INGEST = "material_ingest"
    EXAM_QUESTION_GENERATION = "exam_question_generation"
    EXAM_RESULT_EVALUATION = "exam_result_evaluation"


class AsyncJobStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class AsyncJobTargetType(StrEnum):
    CLASSROOM_MATERIAL = "classroom_material"
    EXAM = "exam"


@dataclass(frozen=True)
class AsyncJobReference:
    job_id: UUID
    job_type: AsyncJobType
    status: AsyncJobStatus
    target_type: AsyncJobTargetType
    target_id: UUID


@dataclass
class AsyncJob(Entity):
    job_type: AsyncJobType
    target_type: AsyncJobTargetType
    target_id: UUID
    requested_by: UUID
    payload: dict[str, Any] = field(default_factory=dict)
    status: AsyncJobStatus = AsyncJobStatus.QUEUED
    result: dict[str, Any] = field(default_factory=dict)
    error_message: str | None = None
    available_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    started_at: datetime | None = None
    completed_at: datetime | None = None
    last_heartbeat_at: datetime | None = None
    attempts: int = 0
    max_attempts: int = 3
    dedupe_key: str | None = None

    @classmethod
    def enqueue(
        cls,
        *,
        job_type: AsyncJobType,
        target_type: AsyncJobTargetType,
        target_id: UUID,
        requested_by: UUID,
        payload: dict[str, Any],
        dedupe_key: str | None = None,
        available_at: datetime | None = None,
        max_attempts: int = 3,
    ) -> AsyncJob:
        return cls(
            job_type=job_type,
            target_type=target_type,
            target_id=target_id,
            requested_by=requested_by,
            payload=dict(payload),
            status=AsyncJobStatus.QUEUED,
            result={},
            error_message=None,
            available_at=available_at or datetime.now(UTC),
            started_at=None,
            completed_at=None,
            last_heartbeat_at=None,
            attempts=0,
            max_attempts=max_attempts,
            dedupe_key=dedupe_key,
        )

    def mark_running(self, *, started_at: datetime | None = None) -> None:
        now = started_at or datetime.now(UTC)
        self.status = AsyncJobStatus.RUNNING
        self.started_at = now
        self.last_heartbeat_at = now
        self.error_message = None
        self.attempts += 1

    def mark_completed(
        self,
        *,
        result: dict[str, Any] | None = None,
        completed_at: datetime | None = None,
    ) -> None:
        self.status = AsyncJobStatus.COMPLETED
        self.result = dict(result or {})
        self.error_message = None
        self.completed_at = completed_at or datetime.now(UTC)
        self.last_heartbeat_at = self.completed_at

    def mark_failed(
        self,
        *,
        error_message: str,
        completed_at: datetime | None = None,
    ) -> None:
        self.status = AsyncJobStatus.FAILED
        self.error_message = error_message[:ASYNC_JOB_ERROR_MESSAGE_MAX_LENGTH]
        self.completed_at = completed_at or datetime.now(UTC)
        self.last_heartbeat_at = self.completed_at

    def touch_heartbeat(self, *, occurred_at: datetime | None = None) -> None:
        self.last_heartbeat_at = occurred_at or datetime.now(UTC)

    def to_reference(self) -> AsyncJobReference:
        return AsyncJobReference(
            job_id=self.id,
            job_type=self.job_type,
            status=self.status,
            target_type=self.target_type,
            target_id=self.target_id,
        )
