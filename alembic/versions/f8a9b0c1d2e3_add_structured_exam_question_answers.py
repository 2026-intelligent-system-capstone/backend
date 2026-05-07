"""add structured exam question answers

Revision ID: f8a9b0c1d2e3
Revises: a9c2d4e6f8b0
Create Date: 2026-05-07 18:30:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "f8a9b0c1d2e3"
down_revision = "a9c2d4e6f8b0"
branch_labels = None
depends_on = None


def build_invalid_legacy_rows_validation_sql():
    return sa.text(
        """
        DO $$
        BEGIN
        IF EXISTS (
            WITH multiple_choice_validity AS (
            SELECT
                question.id,
                count(option.option_text) AS option_count,
                count(*) FILTER (
                    WHERE option.option_text = question.correct_answer_text
                ) AS correct_option_count
            FROM t_exam_question AS question
            LEFT JOIN LATERAL json_array_elements_text(
                question.answer_options
            ) AS option(option_text) ON TRUE
            WHERE question.question_type = 'multiple_choice'
            GROUP BY question.id
        ),
        invalid_legacy_questions AS (
            SELECT id
            FROM multiple_choice_validity
            WHERE option_count < 2 OR correct_option_count != 1
            UNION ALL
            SELECT id
            FROM t_exam_question
            WHERE question_type = 'subjective'
              AND nullif(correct_answer_text, '') IS NULL
            UNION ALL
            SELECT id
            FROM t_exam_question
            WHERE question_type = 'oral'
              AND nullif(rubric_text, '') IS NULL
            )
            SELECT 1 FROM invalid_legacy_questions
        ) THEN
            RAISE EXCEPTION 'invalid legacy exam question rows';
        END IF;
        END $$
        """
    )


def build_structured_answer_backfill_sql():
    return [
        sa.text(
            """
            WITH option_rows AS (
                SELECT
                    question.id AS question_id,
                    option.option_text,
                    option.ordinality::text AS option_id,
                    option.ordinality
                FROM t_exam_question AS question
                CROSS JOIN LATERAL json_array_elements_text(
                    question.answer_options
                ) WITH ORDINALITY AS option(option_text, ordinality)
                WHERE question.question_type = 'multiple_choice'
            ),
            grouped_options AS (
                SELECT
                    question_id,
                    json_agg(
                        json_build_object(
                            'id', option_id,
                            'label', option_id,
                            'text', option_text,
                            'is_correct', option_text = correct_answer_text,
                            'explanation', NULL
                        )
                        ORDER BY ordinality
                    ) AS options_data,
                    max(option_id) FILTER (
                        WHERE option_text = correct_answer_text
                    ) AS correct_option_id
                FROM option_rows
                JOIN t_exam_question AS question ON question.id = question_id
                GROUP BY question_id
            )
            UPDATE t_exam_question AS question
            SET answer_options_data = coalesce(
                    grouped_options.options_data,
                    '[]'::json
                ),
                answer_key_data = json_build_object(
                    'type', 'multiple_choice',
                    'correct_option_ids', CASE
                        WHEN grouped_options.correct_option_id IS NOT NULL
                        THEN json_build_array(grouped_options.correct_option_id)
                        ELSE json_build_array()
                    END,
                    'model_answer', NULL,
                    'acceptable_answers', json_build_array(),
                    'required_keywords', json_build_array(),
                    'expected_points', json_build_array(),
                    'follow_up_questions', json_build_array()
                ),
                rubric_data = json_build_object(
                    'criteria', CASE
                        WHEN nullif(question.rubric_text, '') IS NOT NULL
                        THEN json_build_array(
                            json_build_object(
                                'name', '객관식 평가 기준',
                                'description', question.rubric_text,
                                'points', question.max_score
                            )
                        )
                        ELSE json_build_array()
                    END,
                    'evidence_policy', NULL
                )
            FROM grouped_options
            WHERE question.id = grouped_options.question_id
            """
        ),
        sa.text(
            """
            UPDATE t_exam_question
            SET answer_key_data = json_build_object(
                    'type', 'subjective',
                    'correct_option_ids', json_build_array(),
                    'model_answer', nullif(correct_answer_text, ''),
                    'acceptable_answers', json_build_array(),
                    'required_keywords', json_build_array(),
                    'expected_points', json_build_array(),
                    'follow_up_questions', json_build_array()
                ),
                rubric_data = json_build_object(
                    'criteria', CASE
                        WHEN nullif(rubric_text, '') IS NOT NULL
                        THEN json_build_array(
                            json_build_object(
                                'name', '주관식 평가 기준',
                                'description', rubric_text,
                                'points', max_score
                            )
                        )
                        ELSE json_build_array()
                    END,
                    'evidence_policy', NULL
                )
            WHERE question_type = 'subjective'
            """
        ),
        sa.text(
            """
            UPDATE t_exam_question
            SET answer_key_data = json_build_object(
                    'type', 'oral',
                    'correct_option_ids', json_build_array(),
                    'model_answer', NULL,
                    'acceptable_answers', json_build_array(),
                    'required_keywords', json_build_array(),
                    'expected_points', json_build_array(),
                    'follow_up_questions', json_build_array()
                ),
                rubric_data = json_build_object(
                    'criteria', CASE
                        WHEN nullif(rubric_text, '') IS NOT NULL
                        THEN json_build_array(
                            json_build_object(
                                'name', '구술 평가 기준',
                                'description', rubric_text,
                                'points', max_score
                            )
                        )
                        ELSE json_build_array()
                    END,
                    'evidence_policy', NULL
                )
            WHERE question_type = 'oral'
            """
        ),
    ]


def upgrade() -> None:
    op.execute(build_invalid_legacy_rows_validation_sql())

    op.add_column(
        "t_exam_question",
        sa.Column(
            "answer_options_data",
            sa.JSON(),
            nullable=False,
            server_default=sa.text("'[]'::json"),
        ),
    )
    op.add_column(
        "t_exam_question",
        sa.Column(
            "answer_key_data",
            sa.JSON(),
            nullable=False,
            server_default=sa.text("'{}'::json"),
        ),
    )
    op.add_column(
        "t_exam_question",
        sa.Column(
            "rubric_data",
            sa.JSON(),
            nullable=False,
            server_default=sa.text("'{}'::json"),
        ),
    )

    for statement in build_structured_answer_backfill_sql():
        op.execute(statement)

    for column_name in (
        "answer_options_data",
        "answer_key_data",
        "rubric_data",
    ):
        op.alter_column(
            "t_exam_question",
            column_name,
            server_default=None,
            existing_type=sa.JSON(),
            existing_nullable=False,
        )


def downgrade() -> None:
    op.drop_column("t_exam_question", "rubric_data")
    op.drop_column("t_exam_question", "answer_key_data")
    op.drop_column("t_exam_question", "answer_options_data")
