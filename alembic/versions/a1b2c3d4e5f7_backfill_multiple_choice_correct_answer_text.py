"""backfill multiple choice correct answer text

Revision ID: a1b2c3d4e5f7
Revises: f4b7c2d1a9e3
Create Date: 2026-04-13 23:55:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "a1b2c3d4e5f7"
down_revision = "f4b7c2d1a9e3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        sa.text(
            """
            UPDATE t_exam_question
            SET correct_answer_text = nullif(answer_key, '')
            WHERE question_type = 'multiple_choice'
              AND correct_answer_text IS NULL
              AND nullif(answer_key, '') IS NOT NULL
            """
        )
    )


def downgrade() -> None:
    op.execute(
        sa.text(
            """
            UPDATE t_exam_question
            SET correct_answer_text = NULL
            WHERE question_type = 'multiple_choice'
              AND correct_answer_text = nullif(answer_key, '')
            """
        )
    )
