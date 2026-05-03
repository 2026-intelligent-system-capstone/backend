"""add exam week column

Revision ID: 747f67b6ea68
Revises: 6f0d9c4b7a21
Create Date: 2026-04-02 16:17:41.336058
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision = "747f67b6ea68"
down_revision = "6f0d9c4b7a21"
branch_labels = None
depends_on = None


TEMPORARY_WEEK_DEFAULT = 1


def upgrade() -> None:
    op.add_column(
        "t_exam",
        sa.Column(
            "week",
            sa.Integer(),
            nullable=True,
            server_default=sa.text(str(TEMPORARY_WEEK_DEFAULT)),
        ),
    )
    op.execute(
        sa.text("UPDATE t_exam SET week = :week WHERE week IS NULL").bindparams(
            week=TEMPORARY_WEEK_DEFAULT
        )
    )
    op.alter_column(
        "t_exam",
        "week",
        existing_type=sa.Integer(),
        nullable=False,
        server_default=None,
    )


def downgrade() -> None:
    op.drop_column("t_exam", "week")
