"""Remove OAuth fields from user

Revision ID: 693ae09dc797
Revises: e1ceb3bffcd2
Create Date: 2026-03-24 00:00:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision = "693ae09dc797"
down_revision = "e1ceb3bffcd2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        sa.text(
            "UPDATE t_user "
            "SET password = '__oauth_removed__' "
            "WHERE password IS NULL"
        )
    )
    op.alter_column(
        "t_user", "password", existing_type=sa.String(255), nullable=False
    )
    op.drop_column("t_user", "oauth_provider")
    op.drop_column("t_user", "oauth_id")


def downgrade() -> None:
    op.add_column(
        "t_user",
        sa.Column("oauth_id", sa.String(length=255), nullable=True),
    )
    op.add_column(
        "t_user",
        sa.Column("oauth_provider", sa.String(length=50), nullable=True),
    )
    op.alter_column(
        "t_user", "password", existing_type=sa.String(255), nullable=True
    )
