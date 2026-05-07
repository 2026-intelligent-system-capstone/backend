from uuid import UUID

from sqlalchemy import (
    JSON,
    CheckConstraint,
    Column,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.types import TypeDecorator

from app.exam.domain.entity import (
    BloomLevel,
    ExamDifficulty,
    ExamGenerationStatus,
    ExamQuestionAnswerKey,
    ExamQuestionAnswerOption,
    ExamQuestionRubric,
    ExamQuestionRubricCriterion,
    ExamQuestionStatus,
    ExamQuestionType,
    ExamResultStatus,
    ExamSessionStatus,
    ExamStatus,
    ExamTurnEventType,
    ExamTurnRole,
    ExamType,
)
from core.db.sqlalchemy.models.base import BaseTable, metadata


class StructuredAnswerOptionsJSON(TypeDecorator):
    impl = JSON
    cache_ok = True

    def _parse_bool(self, value) -> bool:
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            normalized = value.strip().lower()
            if normalized == "true":
                return True
            if normalized == "false":
                return False
        return False

    def process_bind_param(self, value, dialect):
        del dialect
        if value is None:
            return []
        return [
            {
                "id": option.id,
                "label": option.label,
                "text": option.text,
                "is_correct": option.is_correct,
                "explanation": option.explanation,
            }
            for option in value
        ]

    def process_result_value(self, value, dialect):
        del dialect
        return [
            ExamQuestionAnswerOption(
                id=str(option.get("id") or ""),
                label=str(option.get("label") or ""),
                text=str(option.get("text") or ""),
                is_correct=self._parse_bool(option.get("is_correct", False)),
                explanation=option.get("explanation"),
            )
            for option in value or []
        ]


class StructuredAnswerKeyJSON(TypeDecorator):
    impl = JSON
    cache_ok = True

    def process_bind_param(self, value, dialect):
        del dialect
        if value is None:
            return {}
        return {
            "type": value.type.value,
            "correct_option_ids": list(value.correct_option_ids),
            "model_answer": value.model_answer,
            "acceptable_answers": list(value.acceptable_answers),
            "required_keywords": list(value.required_keywords),
            "expected_points": list(value.expected_points),
            "follow_up_questions": list(value.follow_up_questions),
        }

    def process_result_value(self, value, dialect):
        del dialect
        if not value:
            return None
        raw_type = value.get("type")
        if raw_type is None:
            return None
        return ExamQuestionAnswerKey(
            type=ExamQuestionType(raw_type),
            correct_option_ids=list(value.get("correct_option_ids") or []),
            model_answer=value.get("model_answer"),
            acceptable_answers=list(value.get("acceptable_answers") or []),
            required_keywords=list(value.get("required_keywords") or []),
            expected_points=list(value.get("expected_points") or []),
            follow_up_questions=list(value.get("follow_up_questions") or []),
        )


class StructuredRubricJSON(TypeDecorator):
    impl = JSON
    cache_ok = True

    def process_bind_param(self, value, dialect):
        del dialect
        if value is None:
            return {}
        return {
            "criteria": [
                {
                    "name": criterion.name,
                    "description": criterion.description,
                    "points": criterion.points,
                }
                for criterion in value.criteria
            ],
            "evidence_policy": value.evidence_policy,
        }

    def process_result_value(self, value, dialect):
        del dialect
        if not value:
            return ExamQuestionRubric()
        return ExamQuestionRubric(
            criteria=[
                ExamQuestionRubricCriterion(
                    name=str(criterion.get("name") or ""),
                    description=str(criterion.get("description") or ""),
                    points=float(criterion.get("points") or 0),
                )
                for criterion in value.get("criteria") or []
            ],
            evidence_policy=value.get("evidence_policy"),
        )


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
    Column("question_count", Integer, nullable=False, default=1),
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
        default=ExamDifficulty.MEDIUM.value,
    ),
    Column("starts_at", DateTime(timezone=True), nullable=False),
    Column("ends_at", DateTime(timezone=True), nullable=False),
    Column("max_attempts", Integer, nullable=False, default=1),
    Column("max_follow_ups", Integer, nullable=False, default=2),
    Column(
        "generation_status",
        Enum(
            ExamGenerationStatus,
            native_enum=False,
            values_callable=lambda enum_cls: [
                member.value for member in enum_cls
            ],
            validate_strings=True,
            length=50,
        ),
        nullable=False,
        default=ExamGenerationStatus.IDLE.value,
    ),
    Column("generation_error", String(1000), nullable=True),
    Column("generation_job_id", PG_UUID(as_uuid=True), nullable=True),
    Column("generation_requested_at", DateTime(timezone=True), nullable=True),
    Column("generation_completed_at", DateTime(timezone=True), nullable=True),
    CheckConstraint(
        "max_follow_ups >= 0",
        name="ck_t_exam_max_follow_ups_non_negative",
    ),
    CheckConstraint(
        "question_count BETWEEN 1 AND 30",
        name="ck_t_exam_question_count_range",
    ),
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
    Column("max_score", Float(), nullable=False, default=1.0),
    Column(
        "question_type",
        Enum(
            ExamQuestionType,
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
    Column("intent_text", String(5000), nullable=False),
    Column("rubric_text", String(12000), nullable=False),
    Column("answer_options", JSON(), nullable=False, default=list),
    Column("correct_answer_text", String(2000), nullable=True),
    Column(
        "answer_options_data",
        StructuredAnswerOptionsJSON(),
        nullable=False,
        default=list,
    ),
    Column(
        "answer_key_data",
        StructuredAnswerKeyJSON(),
        nullable=False,
        default=dict,
    ),
    Column(
        "rubric_data",
        StructuredRubricJSON(),
        nullable=False,
        default=dict,
    ),
    Column("scope_text", String(1000), nullable=True),
    Column("evaluation_objective", String(2000), nullable=True),
    Column("answer_key", String(5000), nullable=True),
    Column("scoring_criteria", String(5000), nullable=True),
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
    CheckConstraint(
        "max_score > 0",
        name="ck_t_exam_question_max_score_positive",
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
    UniqueConstraint("exam_id", "student_id", "attempt_number"),
)

Index(
    "ix_t_exam_session_single_in_progress",
    exam_session_table.c.exam_id,
    exam_session_table.c.student_id,
    unique=True,
    postgresql_where=(
        exam_session_table.c.status == ExamSessionStatus.IN_PROGRESS.value
    ),
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
    Column("overall_score", Float(), nullable=True),
    Column("summary", String(2000), nullable=True),
    Column("strengths", JSON(), nullable=False, default=list),
    Column("weaknesses", JSON(), nullable=False, default=list),
    Column("improvement_suggestions", JSON(), nullable=False, default=list),
)

exam_result_criterion_table = BaseTable(
    "t_exam_result_criterion",
    metadata,
    Column("id", PG_UUID(as_uuid=True), primary_key=True),
    Column(
        "result_id",
        PG_UUID(as_uuid=True),
        ForeignKey("t_exam_result.id", ondelete="CASCADE"),
        nullable=False,
    ),
    Column(
        "criterion_id",
        PG_UUID(as_uuid=True),
        ForeignKey("t_exam_criterion.id", ondelete="CASCADE"),
        nullable=False,
    ),
    Column("score", Float(), nullable=True),
    Column("feedback", String(2000), nullable=True),
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
