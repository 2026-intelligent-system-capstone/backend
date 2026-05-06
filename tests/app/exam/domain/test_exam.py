from datetime import UTC, datetime, timedelta
from uuid import UUID

import pytest

from app.exam.domain.entity import (
    Exam,
    ExamDifficulty,
    ExamQuestion,
    ExamQuestionAnswerKey,
    ExamQuestionAnswerOption,
    ExamQuestionRubric,
    ExamQuestionRubricCriterion,
    ExamQuestionStatus,
    ExamQuestionType,
    ExamType,
)

CLASSROOM_ID = UUID("22222222-2222-2222-2222-222222222222")
NOW = datetime.now(UTC)
STARTS_AT = NOW - timedelta(hours=1)
ENDS_AT = NOW + timedelta(hours=1)


def test_create_exam_stores_question_count_and_difficulty():
    exam = Exam.create(
        classroom_id=CLASSROOM_ID,
        title="중간 평가",
        description="1주차 범위 평가",
        exam_type=ExamType.MIDTERM,
        duration_minutes=60,
        starts_at=STARTS_AT,
        ends_at=ENDS_AT,
        max_attempts=1,
        week=1,
        question_count=12,
        difficulty=ExamDifficulty.HARD,
        criteria=[],
    )

    assert exam.question_count == 12
    assert exam.difficulty is ExamDifficulty.HARD


@pytest.mark.parametrize("question_count", [0, 31])
def test_create_exam_rejects_invalid_question_count(question_count):
    with pytest.raises(
        ValueError,
        match="question_count must be between 1 and 30",
    ):
        Exam.create(
            classroom_id=CLASSROOM_ID,
            title="중간 평가",
            description="1주차 범위 평가",
            exam_type=ExamType.MIDTERM,
            duration_minutes=60,
            starts_at=STARTS_AT,
            ends_at=ENDS_AT,
            max_attempts=1,
            week=1,
            question_count=question_count,
            difficulty=ExamDifficulty.MEDIUM,
            criteria=[],
        )


def _question(**overrides):
    defaults = {
        "exam_id": CLASSROOM_ID,
        "question_number": 1,
        "max_score": 10.0,
        "question_type": ExamQuestionType.MULTIPLE_CHOICE,
        "answer_options": ["선택 A", "선택 B"],
        "correct_answer_text": "선택 A",
    }
    return ExamQuestion(**(defaults | overrides))


def test_multiple_choice_accepts_structured_options_and_key_by_id():
    question = _question(
        answer_options_data=[
            ExamQuestionAnswerOption(
                id=" option-a ",
                label="A",
                text="선택 A",
                is_correct=True,
                explanation="정답 설명",
            ),
            ExamQuestionAnswerOption(
                id="option-b",
                label="B",
                text="선택 B",
            ),
        ],
        answer_key_data=ExamQuestionAnswerKey(
            type=ExamQuestionType.MULTIPLE_CHOICE,
            correct_option_ids=[" option-a "],
        ),
    )

    assert question.answer_options_data[0].id == "option-a"
    assert question.answer_key_data is not None
    assert question.answer_key_data.correct_option_ids == ["option-a"]


def test_revise_restores_missing_structured_defaults_for_orm_loaded_question():
    question = _question()
    delattr(question, "answer_options_data")  # noqa: B043
    delattr(question, "answer_key_data")  # noqa: B043
    delattr(question, "rubric_data")  # noqa: B043

    question.revise(question_text="수정된 질문")

    assert question.answer_options_data == []
    assert question.answer_key_data is None
    assert question.rubric_data == ExamQuestionRubric()
    assert question.status is ExamQuestionStatus.REVIEWED


def test_revise_multiple_choice_replaces_structured_options_and_key():
    question = _question(
        answer_options_data=[
            ExamQuestionAnswerOption(
                id="option-a",
                label="A",
                text="선택 A",
                is_correct=True,
            ),
            ExamQuestionAnswerOption(
                id="option-b",
                label="B",
                text="선택 B",
            ),
        ],
        answer_key_data=ExamQuestionAnswerKey(
            type=ExamQuestionType.MULTIPLE_CHOICE,
            correct_option_ids=["option-a"],
        ),
    )

    question.revise(
        answer_options_data=[
            ExamQuestionAnswerOption(
                id=" option-c ",
                label=" C ",
                text=" 선택 C ",
                is_correct=True,
            ),
            ExamQuestionAnswerOption(
                id="option-d",
                label="D",
                text="선택 D",
            ),
        ],
        answer_key_data=ExamQuestionAnswerKey(
            type=ExamQuestionType.MULTIPLE_CHOICE,
            correct_option_ids=[" option-c "],
        ),
    )

    assert question.answer_options_data[0].id == "option-c"
    assert question.answer_options_data[0].label == "C"
    assert question.answer_options_data[0].text == "선택 C"
    assert question.answer_key_data is not None
    assert question.answer_key_data.correct_option_ids == ["option-c"]


def test_revise_to_oral_rejects_stale_structured_options():
    question = _question(
        answer_options_data=[
            ExamQuestionAnswerOption(
                id="option-a",
                label="A",
                text="선택 A",
                is_correct=True,
            ),
            ExamQuestionAnswerOption(
                id="option-b",
                label="B",
                text="선택 B",
            ),
        ],
        answer_key_data=ExamQuestionAnswerKey(
            type=ExamQuestionType.MULTIPLE_CHOICE,
            correct_option_ids=["option-a"],
        ),
    )

    with pytest.raises(
        ValueError,
        match="oral answer_options_data must be empty",
    ):
        question.revise(
            question_type=ExamQuestionType.ORAL,
            answer_key_data=ExamQuestionAnswerKey(
                type=ExamQuestionType.ORAL,
                expected_points=["개념 설명"],
            ),
        )


def test_failed_structured_revise_leaves_original_question_unchanged():
    question = _question(
        answer_options_data=[
            ExamQuestionAnswerOption(
                id="option-a",
                label="A",
                text="선택 A",
                is_correct=True,
            ),
            ExamQuestionAnswerOption(
                id="option-b",
                label="B",
                text="선택 B",
            ),
        ],
        answer_key_data=ExamQuestionAnswerKey(
            type=ExamQuestionType.MULTIPLE_CHOICE,
            correct_option_ids=["option-a"],
        ),
    )
    original_question_type = question.question_type
    original_answer_options_data = list(question.answer_options_data)
    original_answer_key_data = question.answer_key_data
    original_correct_answer_text = question.correct_answer_text
    original_status = question.status

    with pytest.raises(
        ValueError,
        match="oral answer_options_data must be empty",
    ):
        question.revise(
            question_type=ExamQuestionType.ORAL,
            answer_key_data=ExamQuestionAnswerKey(type=ExamQuestionType.ORAL),
            correct_answer_text=None,
        )

    assert question.question_type is original_question_type
    assert question.answer_options_data == original_answer_options_data
    assert question.answer_key_data == original_answer_key_data
    assert question.correct_answer_text == original_correct_answer_text
    assert question.status is original_status


def test_revise_to_oral_clears_structured_options_when_replaced():
    question = _question(
        answer_options_data=[
            ExamQuestionAnswerOption(
                id="option-a",
                label="A",
                text="선택 A",
                is_correct=True,
            ),
            ExamQuestionAnswerOption(
                id="option-b",
                label="B",
                text="선택 B",
            ),
        ],
        answer_key_data=ExamQuestionAnswerKey(
            type=ExamQuestionType.MULTIPLE_CHOICE,
            correct_option_ids=["option-a"],
        ),
    )

    question.revise(
        question_type=ExamQuestionType.ORAL,
        answer_options_data=[],
        answer_key_data=ExamQuestionAnswerKey(
            type=ExamQuestionType.ORAL,
            expected_points=[" 개념 설명 "],
        ),
    )

    assert question.answer_options_data == []
    assert question.answer_key_data is not None
    assert question.answer_key_data.expected_points == ["개념 설명"]


def test_multiple_choice_blank_structured_option_label_raises_value_error():
    with pytest.raises(ValueError, match="option label must not be empty"):
        _question(
            answer_options_data=[
                ExamQuestionAnswerOption(
                    id="option-a",
                    label=" ",
                    text="선택 A",
                    is_correct=True,
                ),
                ExamQuestionAnswerOption(
                    id="option-b",
                    label="B",
                    text="선택 B",
                ),
            ],
            answer_key_data=ExamQuestionAnswerKey(
                type=ExamQuestionType.MULTIPLE_CHOICE,
                correct_option_ids=["option-a"],
            ),
        )


def test_multiple_choice_blank_structured_option_text_raises_value_error():
    with pytest.raises(ValueError, match="option text must not be empty"):
        _question(
            answer_options_data=[
                ExamQuestionAnswerOption(
                    id="option-a",
                    label="A",
                    text=" ",
                    is_correct=True,
                ),
                ExamQuestionAnswerOption(
                    id="option-b",
                    label="B",
                    text="선택 B",
                ),
            ],
            answer_key_data=ExamQuestionAnswerKey(
                type=ExamQuestionType.MULTIPLE_CHOICE,
                correct_option_ids=["option-a"],
            ),
        )


def test_multiple_choice_duplicate_option_id_raises_value_error():
    with pytest.raises(ValueError, match="option id must be unique"):
        _question(
            answer_options_data=[
                ExamQuestionAnswerOption(
                    id="option-a",
                    label="A",
                    text="선택 A",
                    is_correct=True,
                ),
                ExamQuestionAnswerOption(
                    id=" option-a ",
                    label="B",
                    text="선택 B",
                ),
            ],
            answer_key_data=ExamQuestionAnswerKey(
                type=ExamQuestionType.MULTIPLE_CHOICE,
                correct_option_ids=["option-a"],
            ),
        )


def test_multiple_choice_missing_correct_option_id_raises_value_error():
    with pytest.raises(
        ValueError,
        match="correct_option_ids must reference existing answer_options_data",
    ):
        _question(
            answer_options_data=[
                ExamQuestionAnswerOption(
                    id="option-a",
                    label="A",
                    text="선택 A",
                    is_correct=True,
                ),
                ExamQuestionAnswerOption(
                    id="option-b",
                    label="B",
                    text="선택 B",
                ),
            ],
            answer_key_data=ExamQuestionAnswerKey(
                type=ExamQuestionType.MULTIPLE_CHOICE,
                correct_option_ids=["option-c"],
            ),
        )


def test_structured_choice_ignores_legacy_correct_answer_text_match():
    question = _question(
        answer_options=["레거시 선택"],
        correct_answer_text=None,
        answer_options_data=[
            ExamQuestionAnswerOption(
                id="option-a",
                label="A",
                text="선택 A",
                is_correct=True,
            ),
            ExamQuestionAnswerOption(
                id="option-b",
                label="B",
                text="선택 B",
            ),
        ],
        answer_key_data=ExamQuestionAnswerKey(
            type=ExamQuestionType.MULTIPLE_CHOICE,
            correct_option_ids=["option-a"],
        ),
    )

    assert question.correct_answer_text is None
    assert question.answer_key_data is not None
    assert question.answer_key_data.correct_option_ids == ["option-a"]


def test_subjective_requires_model_answer():
    with pytest.raises(ValueError, match="subjective model_answer is required"):
        _question(
            question_type=ExamQuestionType.SUBJECTIVE,
            answer_options=[],
            correct_answer_text=None,
            answer_key_data=ExamQuestionAnswerKey(
                type=ExamQuestionType.SUBJECTIVE,
                model_answer="  ",
            ),
        )


def test_subjective_normalizes_acceptable_answers_and_required_keywords():
    question = _question(
        question_type=ExamQuestionType.SUBJECTIVE,
        answer_options=[],
        correct_answer_text=None,
        answer_key_data=ExamQuestionAnswerKey(
            type=ExamQuestionType.SUBJECTIVE,
            model_answer="  모범 답안  ",
            acceptable_answers=[" 답안 A ", "", "답안 B"],
            required_keywords=[" 핵심어 ", "  ", "개념"],
        ),
    )

    assert question.answer_key_data is not None
    assert question.answer_key_data.model_answer == "모범 답안"
    assert question.answer_key_data.acceptable_answers == ["답안 A", "답안 B"]
    assert question.answer_key_data.required_keywords == ["핵심어", "개념"]


def test_oral_does_not_require_fixed_model_answer():
    question = _question(
        question_type=ExamQuestionType.ORAL,
        answer_options=[],
        correct_answer_text="ignored",
        answer_key_data=ExamQuestionAnswerKey(
            type=ExamQuestionType.ORAL,
            expected_points=["개념 설명"],
        ),
    )

    assert question.correct_answer_text is None
    assert question.answer_key_data is not None
    assert question.answer_key_data.model_answer is None


def test_oral_requires_expected_points_or_rubric_criteria():
    with pytest.raises(
        ValueError,
        match="oral questions require expected_points or rubric criteria",
    ):
        _question(
            question_type=ExamQuestionType.ORAL,
            answer_options=[],
            correct_answer_text=None,
            answer_key_data=ExamQuestionAnswerKey(type=ExamQuestionType.ORAL),
        )


def test_oral_accepts_rubric_criteria_without_expected_points():
    question = _question(
        question_type=ExamQuestionType.ORAL,
        answer_options=[],
        correct_answer_text=None,
        answer_key_data=ExamQuestionAnswerKey(type=ExamQuestionType.ORAL),
        rubric_data=ExamQuestionRubric(
            criteria=[
                ExamQuestionRubricCriterion(
                    name="개념 이해",
                    description="핵심 개념을 설명한다.",
                    points=5.0,
                )
            ],
        ),
    )

    assert question.rubric_data.criteria[0].name == "개념 이해"


@pytest.mark.parametrize(
    ("criterion", "message"),
    [
        (
            ExamQuestionRubricCriterion(
                name=" ",
                description="핵심 개념을 설명한다.",
                points=5.0,
            ),
            "rubric criterion name must not be empty",
        ),
        (
            ExamQuestionRubricCriterion(
                name="개념 이해",
                description=" ",
                points=5.0,
            ),
            "rubric criterion description must not be empty",
        ),
        (
            ExamQuestionRubricCriterion(
                name="개념 이해",
                description="핵심 개념을 설명한다.",
                points=0,
            ),
            "rubric criterion points must be greater than 0",
        ),
    ],
)
def test_oral_rejects_invalid_rubric_criteria(criterion, message):
    with pytest.raises(ValueError, match=message):
        _question(
            question_type=ExamQuestionType.ORAL,
            answer_options=[],
            correct_answer_text=None,
            answer_key_data=ExamQuestionAnswerKey(type=ExamQuestionType.ORAL),
            rubric_data=ExamQuestionRubric(criteria=[criterion]),
        )


def test_oral_normalizes_valid_rubric_criteria():
    question = _question(
        question_type=ExamQuestionType.ORAL,
        answer_options=[],
        correct_answer_text=None,
        answer_key_data=ExamQuestionAnswerKey(type=ExamQuestionType.ORAL),
        rubric_data=ExamQuestionRubric(
            criteria=[
                ExamQuestionRubricCriterion(
                    name=" 개념 이해 ",
                    description=" 핵심 개념을 설명한다. ",
                    points=5.0,
                )
            ],
        ),
    )

    assert question.rubric_data.criteria[0] == ExamQuestionRubricCriterion(
        name="개념 이해",
        description="핵심 개념을 설명한다.",
        points=5.0,
    )


def test_oral_normalizes_follow_up_questions():
    question = _question(
        question_type=ExamQuestionType.ORAL,
        answer_options=[],
        correct_answer_text=None,
        answer_key_data=ExamQuestionAnswerKey(
            type=ExamQuestionType.ORAL,
            expected_points=["개념 설명"],
            follow_up_questions=[" 추가 질문 1 ", "", "추가 질문 2"],
        ),
    )

    assert question.answer_key_data is not None
    assert question.answer_key_data.follow_up_questions == [
        "추가 질문 1",
        "추가 질문 2",
    ]
