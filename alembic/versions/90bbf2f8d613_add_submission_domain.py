"""add submission domain

Revision ID: 90bbf2f8d613
Revises: 98f0d64f3f11
Create Date: 2026-03-26 15:40:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "90bbf2f8d613"
down_revision = "98f0d64f3f11"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "t_submission",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("exam_id", sa.UUID(), nullable=False),
        sa.Column("student_id", sa.UUID(), nullable=False),
        sa.Column("answer_text", sa.String(length=10000), nullable=False),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("version_id", sa.BigInteger(), nullable=False),
        sa.ForeignKeyConstraint(["exam_id"], ["t_exam.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["student_id"], ["t_user.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("t_submission")
