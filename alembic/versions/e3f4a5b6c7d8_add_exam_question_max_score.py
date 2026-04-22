"""add exam question max score

Revision ID: e3f4a5b6c7d8
Revises: d7e8f9a0b1c2
Create Date: 2026-04-15 11:20:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "e3f4a5b6c7d8"
down_revision = "d7e8f9a0b1c2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "t_exam_question",
        sa.Column(
            "max_score",
            sa.Float(),
            nullable=False,
            server_default=sa.text("1.0"),
        ),
    )
    op.execute(
        sa.text(
            """
            UPDATE t_exam_question
            SET max_score = 1.0
            WHERE max_score IS NULL
            """
        )
    )
    op.create_check_constraint(
        "ck_t_exam_question_max_score_positive",
        "t_exam_question",
        condition="max_score > 0",
    )
    op.alter_column(
        "t_exam_question",
        "max_score",
        existing_type=sa.Float(),
        server_default=None,
        existing_nullable=False,
    )


def downgrade() -> None:
    op.drop_constraint(
        "ck_t_exam_question_max_score_positive",
        "t_exam_question",
        type_="check",
    )
    op.drop_column("t_exam_question", "max_score")
