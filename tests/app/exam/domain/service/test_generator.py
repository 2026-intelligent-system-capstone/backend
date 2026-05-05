import pytest

from app.exam.domain.entity import BloomLevel
from app.exam.domain.service import (
    ExamQuestionGenerationLevelWeight,
    allocate_bloom_weight_counts,
)


def test_allocate_bloom_weight_counts_normalizes_weights():
    counts = allocate_bloom_weight_counts(
        total_question_count=7,
        weights=[
            ExamQuestionGenerationLevelWeight(BloomLevel.REMEMBER, 2),
            ExamQuestionGenerationLevelWeight(BloomLevel.UNDERSTAND, 2),
            ExamQuestionGenerationLevelWeight(BloomLevel.APPLY, 1),
            ExamQuestionGenerationLevelWeight(BloomLevel.ANALYZE, 0),
            ExamQuestionGenerationLevelWeight(BloomLevel.EVALUATE, 0),
            ExamQuestionGenerationLevelWeight(BloomLevel.CREATE, 0),
        ],
    )

    assert [(item.bloom_level, item.count) for item in counts] == [
        (BloomLevel.REMEMBER, 3),
        (BloomLevel.UNDERSTAND, 3),
        (BloomLevel.APPLY, 1),
    ]


def test_allocate_bloom_weight_counts_rejects_all_zero_weights():
    with pytest.raises(ValueError, match="total weight"):
        allocate_bloom_weight_counts(
            total_question_count=5,
            weights=[
                ExamQuestionGenerationLevelWeight(BloomLevel.REMEMBER, 0),
                ExamQuestionGenerationLevelWeight(BloomLevel.UNDERSTAND, 0),
            ],
        )


def test_allocate_bloom_weight_counts_filters_zero_count_levels():
    counts = allocate_bloom_weight_counts(
        total_question_count=2,
        weights=[
            ExamQuestionGenerationLevelWeight(BloomLevel.REMEMBER, 1),
            ExamQuestionGenerationLevelWeight(BloomLevel.UNDERSTAND, 1),
            ExamQuestionGenerationLevelWeight(BloomLevel.APPLY, 1),
        ],
    )

    assert [(item.bloom_level, item.count) for item in counts] == [
        (BloomLevel.REMEMBER, 1),
        (BloomLevel.UNDERSTAND, 1),
    ]


def test_allocate_bloom_weight_counts_allows_single_level_above_five():
    counts = allocate_bloom_weight_counts(
        total_question_count=12,
        weights=[ExamQuestionGenerationLevelWeight(BloomLevel.APPLY, 1)],
    )

    assert [(item.bloom_level, item.count) for item in counts] == [
        (BloomLevel.APPLY, 12),
    ]


def test_allocate_bloom_weight_counts_rejects_duplicate_bloom_levels():
    with pytest.raises(ValueError, match="duplicates"):
        allocate_bloom_weight_counts(
            total_question_count=2,
            weights=[
                ExamQuestionGenerationLevelWeight(BloomLevel.APPLY, 1),
                ExamQuestionGenerationLevelWeight(BloomLevel.APPLY, 1),
            ],
        )


def test_allocate_bloom_weight_counts_rejects_empty_weights():
    with pytest.raises(ValueError, match="empty"):
        allocate_bloom_weight_counts(total_question_count=2, weights=[])
