"""add exam question answer fields

Revision ID: f4b7c2d1a9e3
Revises: c9e1f7a2b3d4
Create Date: 2026-04-13 23:15:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "f4b7c2d1a9e3"
down_revision = "c9e1f7a2b3d4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "t_exam_question",
        sa.Column(
            "answer_options",
            sa.JSON(),
            nullable=False,
            server_default=sa.text("'[]'::json"),
        ),
    )
    op.add_column(
        "t_exam_question",
        sa.Column(
            "correct_answer_text",
            sa.String(length=2000),
            nullable=True,
        ),
    )

    op.execute(
        sa.text(
            """
            UPDATE t_exam_question
            SET answer_options = '[]'::json,
                correct_answer_text = CASE
                    WHEN question_type IN ('subjective', 'multiple_choice')
                        THEN nullif(answer_key, '')
                    ELSE NULL
                END
            """
        )
    )

    op.alter_column(
        "t_exam_question",
        "answer_options",
        server_default=None,
        existing_type=sa.JSON(),
        existing_nullable=False,
    )


def downgrade() -> None:
    op.drop_column("t_exam_question", "correct_answer_text")
    op.drop_column("t_exam_question", "answer_options")
