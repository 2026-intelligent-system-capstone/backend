"""drop submission table

Revision ID: 43fe4a9d465b
Revises: 4bb25466d8f1
Create Date: 2026-04-01 23:16:00.872677
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision = "43fe4a9d465b"
down_revision = "4bb25466d8f1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_table("t_submission")


def downgrade() -> None:
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
        sa.ForeignKeyConstraint(["student_id"], ["t_user.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
