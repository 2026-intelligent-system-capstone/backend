from datetime import UTC, datetime, timedelta
from uuid import UUID

import pytest

from app.exam.domain.entity import (
    Exam,
    ExamDifficulty,
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
