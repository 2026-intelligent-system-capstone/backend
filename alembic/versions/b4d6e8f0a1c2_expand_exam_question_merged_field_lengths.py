"""expand exam question merged field lengths

Revision ID: b4d6e8f0a1c2
Revises: a8b3c7d9e1f2
Create Date: 2026-04-13 16:24:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "b4d6e8f0a1c2"
down_revision = "a8b3c7d9e1f2"
branch_labels = None
depends_on = None


INTENT_TEXT_LENGTH = 5000
RUBRIC_TEXT_LENGTH = 12000


def upgrade() -> None:
    op.alter_column(
        "t_exam_question",
        "intent_text",
        existing_type=sa.String(length=3000),
        type_=sa.String(length=INTENT_TEXT_LENGTH),
        existing_nullable=False,
    )
    op.alter_column(
        "t_exam_question",
        "rubric_text",
        existing_type=sa.String(length=5000),
        type_=sa.String(length=RUBRIC_TEXT_LENGTH),
        existing_nullable=False,
    )


def downgrade() -> None:
    op.alter_column(
        "t_exam_question",
        "rubric_text",
        existing_type=sa.String(length=RUBRIC_TEXT_LENGTH),
        type_=sa.String(length=5000),
        existing_nullable=False,
    )
    op.alter_column(
        "t_exam_question",
        "intent_text",
        existing_type=sa.String(length=INTENT_TEXT_LENGTH),
        type_=sa.String(length=3000),
        existing_nullable=False,
    )
