from uuid import UUID

from sqlalchemy import (
    JSON,
    Boolean,
    Column,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    String,
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.types import TypeDecorator

from app.exam.domain.entity import (
    BloomLevel,
    ExamDifficulty,
    ExamQuestionStatus,
    ExamResultStatus,
    ExamSessionStatus,
    ExamStatus,
    ExamTurnEventType,
    ExamTurnRole,
    ExamType,
)
from core.db.sqlalchemy.models.base import BaseTable, metadata


class UUIDListJSON(TypeDecorator):
    impl = JSON
    cache_ok = True

    def process_bind_param(self, value, dialect):
        del dialect
        if value is None:
            raise TypeError("source_material_ids cannot be null")
        serialized = []
        for item in value:
            if isinstance(item, UUID):
                serialized.append(str(item))
                continue
            if isinstance(item, str):
                serialized.append(str(UUID(item)))
                continue
            raise TypeError("source_material_ids must contain UUID values")
        return serialized

    def process_result_value(self, value, dialect):
        del dialect
        if value is None:
            raise ValueError("source_material_ids cannot be null")
        deserialized = []
        for item in value:
            if isinstance(item, UUID):
                deserialized.append(item)
                continue
            if isinstance(item, str):
                deserialized.append(UUID(item))
                continue
            raise TypeError("source_material_ids must contain UUID strings")
        return deserialized


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
    Column(
        "exam_type",
        Enum(
            ExamType,
            native_enum=False,
            values_callable=lambda enum_cls: [
                member.value for member in enum_cls
            ],
            validate_strings=True,
            length=50,
        ),
        nullable=False,
    ),
    Column(
        "status",
        Enum(
            ExamStatus,
            native_enum=False,
            values_callable=lambda enum_cls: [
                member.value for member in enum_cls
            ],
            validate_strings=True,
            length=50,
        ),
        nullable=False,
    ),
    Column("duration_minutes", Integer, nullable=False),
    Column("week", Integer, nullable=False),
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

exam_question_table = BaseTable(
    "t_exam_question",
    metadata,
    Column("id", PG_UUID(as_uuid=True), primary_key=True),
    Column(
        "exam_id",
        PG_UUID(as_uuid=True),
        ForeignKey("t_exam.id", ondelete="CASCADE"),
        nullable=False,
    ),
    Column("question_number", Integer, nullable=False),
    Column(
        "bloom_level",
        Enum(
            BloomLevel,
            native_enum=False,
            values_callable=lambda enum_cls: [
                member.value for member in enum_cls
            ],
            validate_strings=True,
            length=50,
        ),
        nullable=False,
    ),
    Column(
        "difficulty",
        Enum(
            ExamDifficulty,
            native_enum=False,
            values_callable=lambda enum_cls: [
                member.value for member in enum_cls
            ],
            validate_strings=True,
            length=50,
        ),
        nullable=False,
    ),
    Column("question_text", String(5000), nullable=False),
    Column("scope_text", String(1000), nullable=False),
    Column("evaluation_objective", String(2000), nullable=False),
    Column("answer_key", String(5000), nullable=False),
    Column("scoring_criteria", String(5000), nullable=False),
    Column("source_material_ids", UUIDListJSON(), nullable=False, default=list),
    Column(
        "status",
        Enum(
            ExamQuestionStatus,
            native_enum=False,
            values_callable=lambda enum_cls: [
                member.value for member in enum_cls
            ],
            validate_strings=True,
            length=50,
        ),
        nullable=False,
    ),
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
    Column(
        "status",
        Enum(
            ExamSessionStatus,
            native_enum=False,
            values_callable=lambda enum_cls: [
                member.value for member in enum_cls
            ],
            validate_strings=True,
            length=50,
        ),
        nullable=False,
    ),
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
    Column(
        "status",
        Enum(
            ExamResultStatus,
            native_enum=False,
            values_callable=lambda enum_cls: [
                member.value for member in enum_cls
            ],
            validate_strings=True,
            length=50,
        ),
        nullable=False,
    ),
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
    Column(
        "role",
        Enum(
            ExamTurnRole,
            native_enum=False,
            values_callable=lambda enum_cls: [
                member.value for member in enum_cls
            ],
            validate_strings=True,
            length=50,
        ),
        nullable=False,
    ),
    Column(
        "event_type",
        Enum(
            ExamTurnEventType,
            native_enum=False,
            values_callable=lambda enum_cls: [
                member.value for member in enum_cls
            ],
            validate_strings=True,
            length=50,
        ),
        nullable=False,
    ),
    Column("content", String(10000), nullable=False),
    Column("metadata", JSON(), nullable=False, default=dict),
    Column("created_at", DateTime(timezone=True), nullable=False),
)
