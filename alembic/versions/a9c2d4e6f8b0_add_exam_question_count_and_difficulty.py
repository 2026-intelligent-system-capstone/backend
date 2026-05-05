"""add exam question count and difficulty

Revision ID: a9c2d4e6f8b0
Revises: e6f7a8b9c0d1
Create Date: 2026-05-04 18:00:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "a9c2d4e6f8b0"
down_revision = "e6f7a8b9c0d1"
branch_labels = None
depends_on = None


EXAM_DIFFICULTY_VALUES = ("easy", "medium", "hard")


def upgrade() -> None:
    op.add_column(
        "t_exam",
        sa.Column("question_count", sa.Integer(), nullable=True),
    )
    op.add_column(
        "t_exam",
        sa.Column(
            "difficulty",
            sa.Enum(
                *EXAM_DIFFICULTY_VALUES,
                name="exam_difficulty",
                native_enum=False,
                validate_strings=True,
                length=50,
            ),
            nullable=True,
        ),
    )
    op.execute(
        sa.text(
            """
            UPDATE t_exam AS exam
            SET question_count = LEAST(
                GREATEST(
                    COALESCE(
                        (
                            SELECT COUNT(*)
                            FROM t_exam_question AS question
                            WHERE question.exam_id = exam.id
                            AND question.status != 'deleted'
                        ),
                        0
                    ),
                    1
                ),
                30
            )
            """
        )
    )
    op.execute(sa.text("UPDATE t_exam SET difficulty = 'medium'"))
    op.alter_column("t_exam", "question_count", nullable=False)
    op.alter_column("t_exam", "difficulty", nullable=False)
    op.create_check_constraint(
        "ck_t_exam_question_count_range",
        "t_exam",
        "question_count BETWEEN 1 AND 30",
    )


def downgrade() -> None:
    op.drop_constraint(
        "ck_t_exam_question_count_range",
        "t_exam",
        type_="check",
    )
    op.drop_column("t_exam", "difficulty")
    op.drop_column("t_exam", "question_count")
