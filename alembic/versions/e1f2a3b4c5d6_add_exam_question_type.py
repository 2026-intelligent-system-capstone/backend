"""add exam question type

Revision ID: e1f2a3b4c5d6
Revises: ab12cd34ef56
Create Date: 2026-04-12 18:40:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "e1f2a3b4c5d6"
down_revision = "ab12cd34ef56"
branch_labels = None
depends_on = None


QUESTION_TYPES = ("none", "multiple_choice", "subjective", "oral")


def _build_check_constraint(values: tuple[str, ...]) -> sa.CheckConstraint:
    quoted = ", ".join(f"'{value}'" for value in values)
    return sa.CheckConstraint(
        f"question_type IN ({quoted})",
        name="ck_t_exam_question_question_type",
    )


def upgrade() -> None:
    op.add_column(
        "t_exam_question",
        sa.Column(
            "question_type",
            sa.String(length=50),
            nullable=False,
            server_default="none",
        ),
    )
    op.alter_column(
        "t_exam_question",
        "question_type",
        server_default=None,
    )
    op.create_check_constraint(
        "ck_t_exam_question_question_type",
        "t_exam_question",
        condition=str(_build_check_constraint(QUESTION_TYPES).sqltext),
    )


def downgrade() -> None:
    op.drop_constraint(
        "ck_t_exam_question_question_type",
        "t_exam_question",
        type_="check",
    )
    op.drop_column("t_exam_question", "question_type")
