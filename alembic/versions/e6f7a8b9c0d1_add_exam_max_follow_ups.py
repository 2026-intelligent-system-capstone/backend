"""add exam max follow ups

Revision ID: e6f7a8b9c0d1
Revises: e3f4a5b6c7d8
Create Date: 2026-05-04 17:00:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "e6f7a8b9c0d1"
down_revision = "e3f4a5b6c7d8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "t_exam",
        sa.Column(
            "max_follow_ups",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("2"),
        ),
    )
    op.create_check_constraint(
        "ck_t_exam_max_follow_ups_non_negative",
        "t_exam",
        "max_follow_ups >= 0",
    )
    op.alter_column("t_exam", "max_follow_ups", server_default=None)


def downgrade() -> None:
    op.drop_constraint(
        "ck_t_exam_max_follow_ups_non_negative",
        "t_exam",
        type_="check",
    )
    op.drop_column("t_exam", "max_follow_ups")
