from uuid import UUID

import pytest
from sqlalchemy.sql.sqltypes import Enum as SQLAlchemyEnum

from app.exam.domain.entity import (
    BloomLevel,
    ExamDifficulty,
    ExamQuestion,
    ExamQuestionStatus,
    ExamQuestionType,
    ExamResultStatus,
    ExamSessionStatus,
    ExamStatus,
    ExamTurnEventType,
    ExamTurnRole,
    ExamType,
)
from core.db.sqlalchemy.models.exam import (
    exam_question_table,
    exam_result_criterion_table,
    exam_result_table,
    exam_session_table,
    exam_table,
    exam_turn_table,
)


def assert_enum_column(column, enum_class):
    assert isinstance(column.type, SQLAlchemyEnum)
    assert column.type.enum_class is enum_class
    assert column.type.native_enum is False
    assert column.type.validate_strings is True
    assert column.type.enums == [member.value for member in enum_class]


def test_exam_table_uses_sqlalchemy_enum_columns():
    assert_enum_column(exam_table.c.exam_type, ExamType)
    assert_enum_column(exam_table.c.status, ExamStatus)


def test_exam_table_contains_non_nullable_week_column():
    assert exam_table.c.week.nullable is False


def test_exam_table_contains_non_nullable_max_attempts_column():
    assert exam_table.c.max_attempts.nullable is False
    assert exam_table.c.max_attempts.default is not None
    assert exam_table.c.max_attempts.default.arg == 1


def test_exam_question_table_uses_sqlalchemy_enum_columns():
    assert_enum_column(exam_question_table.c.question_type, ExamQuestionType)
    assert_enum_column(exam_question_table.c.bloom_level, BloomLevel)
    assert_enum_column(exam_question_table.c.difficulty, ExamDifficulty)
    assert_enum_column(exam_question_table.c.status, ExamQuestionStatus)


def test_exam_question_table_contains_merged_intent_and_rubric_columns():
    assert exam_question_table.c.intent_text.nullable is False
    assert exam_question_table.c.intent_text.type.length == 5000
    assert exam_question_table.c.rubric_text.nullable is False
    assert exam_question_table.c.rubric_text.type.length == 12000
    assert exam_question_table.c.answer_options.nullable is False
    assert exam_question_table.c.correct_answer_text.nullable is True
    assert exam_question_table.c.correct_answer_text.type.length == 2000


def test_exam_question_table_keeps_legacy_columns_for_backfill_compatibility():
    assert exam_question_table.c.scope_text.nullable is True
    assert exam_question_table.c.evaluation_objective.nullable is True
    assert exam_question_table.c.answer_key.nullable is True
    assert exam_question_table.c.scoring_criteria.nullable is True


def test_exam_question_table_contains_non_nullable_max_score_column():
    assert exam_question_table.c.max_score.nullable is False
    assert exam_question_table.c.max_score.default is not None
    assert exam_question_table.c.max_score.default.arg == 1.0


def test_exam_question_table_contains_positive_max_score_check_constraint():
    check_constraints = [
        constraint
        for constraint in exam_question_table.constraints
        if constraint.__class__.__name__ == "CheckConstraint"
    ]

    assert any(
        constraint.name == "ck_t_exam_question_max_score_positive"
        and str(constraint.sqltext) == "max_score > 0"
        for constraint in check_constraints
    )


def test_legacy_multiple_choice_question_without_options_still_loads():
    question = ExamQuestion(
        exam_id=UUID("11111111-1111-1111-1111-111111111111"),
        question_number=1,
        max_score=1.0,
        question_type=ExamQuestionType.MULTIPLE_CHOICE,
        bloom_level=BloomLevel.APPLY,
        difficulty=ExamDifficulty.MEDIUM,
        question_text="기존 객관식 문항",
        intent_text="기존 의도",
        rubric_text="기존 루브릭",
        answer_options=[],
        correct_answer_text="회귀",
        source_material_ids=[],
    )

    assert question.question_type is ExamQuestionType.MULTIPLE_CHOICE
    assert question.answer_options == []
    assert question.correct_answer_text == "회귀"


def test_exam_question_table_serializes_source_material_ids_as_json_strings():
    source_material_ids = exam_question_table.c.source_material_ids
    bind_param = source_material_ids.type.process_bind_param
    bind_value = bind_param(
        [
            UUID("99999999-9999-9999-9999-999999999999"),
            UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"),
        ],
        None,
    )

    assert bind_value == [
        "99999999-9999-9999-9999-999999999999",
        "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
    ]


def test_exam_question_table_restores_source_material_ids_as_uuid_list():
    source_material_ids = exam_question_table.c.source_material_ids
    process_result = source_material_ids.type.process_result_value
    result_value = process_result(
        [
            "99999999-9999-9999-9999-999999999999",
            "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
        ],
        None,
    )

    assert result_value == [
        UUID("99999999-9999-9999-9999-999999999999"),
        UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"),
    ]


def test_exam_question_table_rejects_null_source_material_ids_on_bind():
    source_material_ids = exam_question_table.c.source_material_ids
    bind_param = source_material_ids.type.process_bind_param

    with pytest.raises(TypeError, match="source_material_ids cannot be null"):
        bind_param(None, None)


def test_exam_question_table_rejects_invalid_source_material_id_member():
    source_material_ids = exam_question_table.c.source_material_ids
    bind_param = source_material_ids.type.process_bind_param

    with pytest.raises(
        TypeError,
        match="source_material_ids must contain UUID values",
    ):
        bind_param([123], None)


def test_exam_question_table_rejects_invalid_source_material_id_string():
    source_material_ids = exam_question_table.c.source_material_ids
    process_result = source_material_ids.type.process_result_value

    with pytest.raises(
        ValueError,
        match="badly formed hexadecimal UUID string",
    ):
        process_result(["not-a-uuid"], None)


def test_exam_session_and_result_tables_use_sqlalchemy_enum_columns():
    assert_enum_column(exam_session_table.c.status, ExamSessionStatus)
    assert_enum_column(exam_result_table.c.status, ExamResultStatus)


def test_exam_result_table_contains_rich_feedback_columns():
    assert exam_result_table.c.overall_score.nullable is True
    assert exam_result_table.c.summary.type.length == 2000
    assert exam_result_table.c.strengths.nullable is False
    assert exam_result_table.c.weaknesses.nullable is False
    assert exam_result_table.c.improvement_suggestions.nullable is False


def test_exam_result_criterion_table_contains_score_and_feedback_columns():
    assert exam_result_criterion_table.c.result_id.nullable is False
    assert exam_result_criterion_table.c.criterion_id.nullable is False
    assert exam_result_criterion_table.c.score.nullable is True
    assert exam_result_criterion_table.c.feedback.nullable is True
    assert exam_result_criterion_table.c.feedback.type.length == 2000


def test_exam_session_table_contains_unique_attempt_constraint():
    unique_constraints = list(exam_session_table.constraints)

    assert any(
        constraint.__class__.__name__ == "UniqueConstraint"
        and tuple(constraint.columns.keys())
        == ("exam_id", "student_id", "attempt_number")
        for constraint in unique_constraints
    )


def test_exam_session_table_contains_single_in_progress_index():
    assert any(
        index.name == "ix_t_exam_session_single_in_progress"
        and tuple(column.name for column in index.columns)
        == ("exam_id", "student_id")
        and index.unique is True
        for index in exam_session_table.indexes
    )


def test_exam_turn_table_uses_sqlalchemy_enum_columns():
    assert_enum_column(exam_turn_table.c.role, ExamTurnRole)
    assert_enum_column(exam_turn_table.c.event_type, ExamTurnEventType)
