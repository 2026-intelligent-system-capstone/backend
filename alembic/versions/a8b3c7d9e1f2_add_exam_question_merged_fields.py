"""add exam question merged fields

Revision ID: a8b3c7d9e1f2
Revises: f2a4c6d8e0b1
Create Date: 2026-04-13 16:10:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "a8b3c7d9e1f2"
down_revision = "f2a4c6d8e0b1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "t_exam_question",
        sa.Column("intent_text", sa.String(length=3000), nullable=True),
    )
    op.add_column(
        "t_exam_question",
        sa.Column("rubric_text", sa.String(length=5000), nullable=True),
    )

    op.execute(
        sa.text(
            """
            UPDATE t_exam_question
            SET intent_text = trim(
                    both E'\n' FROM concat_ws(
                        E'\n\n',
                        nullif(scope_text, ''),
                        nullif(evaluation_objective, '')
                    )
                ),
                rubric_text = trim(
                    both E'\n' FROM concat_ws(
                        E'\n\n',
                        nullif(answer_key, ''),
                        nullif(scoring_criteria, '')
                    )
                )
            WHERE intent_text IS NULL OR rubric_text IS NULL
            """
        )
    )

    op.alter_column("t_exam_question", "intent_text", nullable=False)
    op.alter_column("t_exam_question", "rubric_text", nullable=False)


def downgrade() -> None:
    op.drop_column("t_exam_question", "rubric_text")
    op.drop_column("t_exam_question", "intent_text")
