"""rename quiz to weekly and add project exam type

Revision ID: b7d5e6a1c2f4
Revises: 747f67b6ea68
Create Date: 2026-04-06 12:00:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision = "b7d5e6a1c2f4"
down_revision = "747f67b6ea68"
branch_labels = None
depends_on = None


OLD_EXAM_TYPES = ("quiz", "midterm", "final", "mock")
NEW_EXAM_TYPES = ("weekly", "midterm", "final", "mock", "project")


def _build_check_constraint(values: tuple[str, ...]) -> sa.CheckConstraint:
    quoted = ", ".join(f"'{value}'" for value in values)
    return sa.CheckConstraint(
        f"exam_type IN ({quoted})",
        name="ck_t_exam_exam_type",
    )


def upgrade() -> None:
    op.execute(
        sa.text(
            "UPDATE t_exam SET exam_type = 'weekly' WHERE exam_type = 'quiz'"
        )
    )
    op.create_check_constraint(
        "ck_t_exam_exam_type",
        "t_exam",
        condition=str(_build_check_constraint(NEW_EXAM_TYPES).sqltext),
    )


def downgrade() -> None:
    op.drop_constraint("ck_t_exam_exam_type", "t_exam", type_="check")
    op.execute(sa.text("DELETE FROM t_exam WHERE exam_type = 'project'"))
    op.execute(
        sa.text(
            "UPDATE t_exam SET exam_type = 'quiz' WHERE exam_type = 'weekly'"
        )
    )
    op.create_check_constraint(
        "ck_t_exam_exam_type",
        "t_exam",
        condition=str(_build_check_constraint(OLD_EXAM_TYPES).sqltext),
    )
