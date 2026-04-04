from uuid import UUID

from sqlalchemy.sql.sqltypes import Enum as SQLAlchemyEnum

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
from core.db.sqlalchemy.models.exam import (
    exam_question_table,
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
    assert column.type.enums == [
        member.value for member in enum_class
    ]


def test_exam_table_uses_sqlalchemy_enum_columns():
    assert_enum_column(exam_table.c.exam_type, ExamType)
    assert_enum_column(exam_table.c.status, ExamStatus)


def test_exam_table_contains_non_nullable_week_column():
    assert exam_table.c.week.nullable is False


def test_exam_question_table_uses_sqlalchemy_enum_columns():
    assert_enum_column(exam_question_table.c.bloom_level, BloomLevel)
    assert_enum_column(exam_question_table.c.difficulty, ExamDifficulty)
    assert_enum_column(exam_question_table.c.status, ExamQuestionStatus)


def test_exam_question_table_serializes_source_material_ids_as_json_strings():
    bind_value = exam_question_table.c.source_material_ids.type.process_bind_param(
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
    result_value = exam_question_table.c.source_material_ids.type.process_result_value(
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
    try:
        exam_question_table.c.source_material_ids.type.process_bind_param(
            None,
            None,
        )
    except TypeError as exc:
        assert str(exc) == "source_material_ids cannot be null"
    else:
        raise AssertionError("TypeError was not raised")


def test_exam_question_table_rejects_invalid_source_material_id_member_on_bind():
    try:
        exam_question_table.c.source_material_ids.type.process_bind_param(
            [123],
            None,
        )
    except TypeError as exc:
        assert str(exc) == "source_material_ids must contain UUID values"
    else:
        raise AssertionError("TypeError was not raised")


def test_exam_question_table_rejects_invalid_source_material_id_string_on_load():
    try:
        exam_question_table.c.source_material_ids.type.process_result_value(
            ["not-a-uuid"],
            None,
        )
    except ValueError as exc:
        assert "badly formed hexadecimal UUID string" in str(exc)
    else:
        raise AssertionError("ValueError was not raised")


def test_exam_session_and_result_tables_use_sqlalchemy_enum_columns():
    assert_enum_column(exam_session_table.c.status, ExamSessionStatus)
    assert_enum_column(exam_result_table.c.status, ExamResultStatus)


def test_exam_turn_table_uses_sqlalchemy_enum_columns():
    assert_enum_column(exam_turn_table.c.role, ExamTurnRole)
    assert_enum_column(exam_turn_table.c.event_type, ExamTurnEventType)
