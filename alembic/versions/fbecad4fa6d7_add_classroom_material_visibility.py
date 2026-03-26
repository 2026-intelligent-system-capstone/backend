"""Add classroom material visibility

Revision ID: fbecad4fa6d7
Revises: ced00c92f824
Create Date: 2026-03-24 22:41:26.116609
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision = "fbecad4fa6d7"
down_revision = "ced00c92f824"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "t_classroom",
        sa.Column(
            "allow_student_material_access",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )
    op.alter_column(
        "t_classroom",
        "allow_student_material_access",
        server_default=None,
    )


def downgrade() -> None:
    op.drop_column("t_classroom", "allow_student_material_access")
