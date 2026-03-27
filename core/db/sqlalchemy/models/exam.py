from sqlalchemy import (
    JSON,
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID

from core.db.sqlalchemy.models.base import BaseTable, metadata

exam_table = BaseTable(
    "t_exam",
    metadata,
    Column("id", PG_UUID(as_uuid=True), primary_key=True),
    Column(
        "classroom_id",
        PG_UUID(as_uuid=True),
        ForeignKey("t_classroom.id", ondelete="CASCADE"),
        nullable=False,
    ),
    Column("title", String(100), nullable=False),
    Column("description", String(1000), nullable=True),
    Column("exam_type", String(50), nullable=False),
    Column("status", String(50), nullable=False),
    Column("duration_minutes", Integer, nullable=False),
    Column("starts_at", DateTime(timezone=True), nullable=False),
    Column("ends_at", DateTime(timezone=True), nullable=False),
    Column("allow_retake", Boolean, nullable=False, default=False),
)

exam_criterion_table = BaseTable(
    "t_exam_criterion",
    metadata,
    Column("id", PG_UUID(as_uuid=True), primary_key=True),
    Column(
        "exam_id",
        PG_UUID(as_uuid=True),
        ForeignKey("t_exam.id", ondelete="CASCADE"),
        nullable=False,
    ),
    Column("title", String(100), nullable=False),
    Column("description", String(1000), nullable=True),
    Column("weight", Integer, nullable=False),
    Column("sort_order", Integer, nullable=False),
    Column("excellent_definition", String(1000), nullable=True),
    Column("average_definition", String(1000), nullable=True),
    Column("poor_definition", String(1000), nullable=True),
)

exam_session_table = BaseTable(
    "t_exam_session",
    metadata,
    Column("id", PG_UUID(as_uuid=True), primary_key=True),
    Column(
        "exam_id",
        PG_UUID(as_uuid=True),
        ForeignKey("t_exam.id", ondelete="CASCADE"),
        nullable=False,
    ),
    Column(
        "student_id",
        PG_UUID(as_uuid=True),
        ForeignKey("t_user.id", ondelete="RESTRICT"),
        nullable=False,
    ),
    Column("status", String(50), nullable=False),
    Column("started_at", DateTime(timezone=True), nullable=False),
    Column("ended_at", DateTime(timezone=True), nullable=True),
    Column("last_activity_at", DateTime(timezone=True), nullable=False),
    Column("expires_at", DateTime(timezone=True), nullable=True),
    Column("attempt_number", Integer(), nullable=False),
    Column("provider_session_id", String(255), nullable=True),
)

exam_result_table = BaseTable(
    "t_exam_result",
    metadata,
    Column("id", PG_UUID(as_uuid=True), primary_key=True),
    Column(
        "exam_id",
        PG_UUID(as_uuid=True),
        ForeignKey("t_exam.id", ondelete="CASCADE"),
        nullable=False,
    ),
    Column(
        "session_id",
        PG_UUID(as_uuid=True),
        ForeignKey("t_exam_session.id", ondelete="CASCADE"),
        nullable=False,
    ),
    Column(
        "student_id",
        PG_UUID(as_uuid=True),
        ForeignKey("t_user.id", ondelete="RESTRICT"),
        nullable=False,
    ),
    Column("status", String(50), nullable=False),
    Column("submitted_at", DateTime(timezone=True), nullable=True),
    Column("overall_score", Integer(), nullable=True),
    Column("summary", String(2000), nullable=True),
)

exam_turn_table = BaseTable(
    "t_exam_turn",
    metadata,
    Column("id", PG_UUID(as_uuid=True), primary_key=True),
    Column(
        "session_id",
        PG_UUID(as_uuid=True),
        ForeignKey("t_exam_session.id", ondelete="CASCADE"),
        nullable=False,
    ),
    Column("sequence", Integer(), nullable=False),
    Column("role", String(50), nullable=False),
    Column("event_type", String(50), nullable=False),
    Column("content", String(10000), nullable=False),
    Column("metadata", JSON(), nullable=False, default=dict),
    Column("created_at", DateTime(timezone=True), nullable=False),
)
