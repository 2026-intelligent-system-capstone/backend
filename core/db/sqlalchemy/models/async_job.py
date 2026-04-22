from sqlalchemy import Column, DateTime, Enum, Integer, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID

from app.async_job.domain.entity import (
    AsyncJobStatus,
    AsyncJobTargetType,
    AsyncJobType,
)
from core.db.sqlalchemy.models.base import BaseTable, metadata

async_job_table = BaseTable(
    "t_async_job",
    metadata,
    Column("id", PG_UUID(as_uuid=True), primary_key=True),
    Column(
        "job_type",
        Enum(
            AsyncJobType,
            native_enum=False,
            values_callable=lambda enum_cls: [
                member.value for member in enum_cls
            ],
            validate_strings=True,
            length=80,
        ),
        nullable=False,
    ),
    Column(
        "status",
        Enum(
            AsyncJobStatus,
            native_enum=False,
            values_callable=lambda enum_cls: [
                member.value for member in enum_cls
            ],
            validate_strings=True,
            length=40,
        ),
        nullable=False,
    ),
    Column(
        "target_type",
        Enum(
            AsyncJobTargetType,
            native_enum=False,
            values_callable=lambda enum_cls: [
                member.value for member in enum_cls
            ],
            validate_strings=True,
            length=80,
        ),
        nullable=False,
    ),
    Column("target_id", PG_UUID(as_uuid=True), nullable=False),
    Column("payload", JSONB, nullable=False, default=dict),
    Column("result", JSONB, nullable=False, default=dict),
    Column("error_message", String(1000), nullable=True),
    Column("requested_by", PG_UUID(as_uuid=True), nullable=False),
    Column("available_at", DateTime(timezone=True), nullable=False),
    Column("started_at", DateTime(timezone=True), nullable=True),
    Column("completed_at", DateTime(timezone=True), nullable=True),
    Column("last_heartbeat_at", DateTime(timezone=True), nullable=True),
    Column("attempts", Integer, nullable=False, default=0),
    Column("max_attempts", Integer, nullable=False, default=3),
    Column("dedupe_key", String(255), nullable=True),
)
