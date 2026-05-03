"""make legacy exam question fields nullable

Revision ID: d7e8f9a0b1c2
Revises: a1b2c3d4e5f7
Create Date: 2026-04-15 00:45:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "d7e8f9a0b1c2"
down_revision = "a1b2c3d4e5f7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column(
        "t_exam_question",
        "scope_text",
        existing_type=sa.String(length=1000),
        nullable=True,
    )
    op.alter_column(
        "t_exam_question",
        "evaluation_objective",
        existing_type=sa.String(length=2000),
        nullable=True,
    )
    op.alter_column(
        "t_exam_question",
        "answer_key",
        existing_type=sa.String(length=5000),
        nullable=True,
    )
    op.alter_column(
        "t_exam_question",
        "scoring_criteria",
        existing_type=sa.String(length=5000),
        nullable=True,
    )


def downgrade() -> None:
    op.execute(
        sa.text(
            """
            UPDATE t_exam_question
            SET scope_text = left(
                    coalesce(nullif(scope_text, ''), intent_text),
                    1000
                ),
                evaluation_objective = left(
                    coalesce(nullif(evaluation_objective, ''), intent_text),
                    2000
                ),
                answer_key = left(
                    coalesce(nullif(answer_key, ''), rubric_text),
                    5000
                ),
                scoring_criteria = left(
                    coalesce(nullif(scoring_criteria, ''), rubric_text),
                    5000
                )
            WHERE scope_text IS NULL
               OR evaluation_objective IS NULL
               OR answer_key IS NULL
               OR scoring_criteria IS NULL
            """
        )
    )

    op.alter_column(
        "t_exam_question",
        "scope_text",
        existing_type=sa.String(length=1000),
        nullable=False,
    )
    op.alter_column(
        "t_exam_question",
        "evaluation_objective",
        existing_type=sa.String(length=2000),
        nullable=False,
    )
    op.alter_column(
        "t_exam_question",
        "answer_key",
        existing_type=sa.String(length=5000),
        nullable=False,
    )
    op.alter_column(
        "t_exam_question",
        "scoring_criteria",
        existing_type=sa.String(length=5000),
        nullable=False,
    )
