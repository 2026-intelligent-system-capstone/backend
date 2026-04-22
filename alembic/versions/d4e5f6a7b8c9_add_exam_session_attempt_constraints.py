"""add exam session attempt constraints

Revision ID: d4e5f6a7b8c9
Revises: c1a2b3d4e5f6
Create Date: 2026-04-07 15:10:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision = "d4e5f6a7b8c9"
down_revision = "c1a2b3d4e5f6"
branch_labels = None
depends_on = None


UNIQUE_ATTEMPT_CONSTRAINT_NAME = "uq_t_exam_session_exam_student_attempt"
SINGLE_IN_PROGRESS_INDEX_NAME = "ix_t_exam_session_single_in_progress"
DUPLICATE_ATTEMPT_ERROR_MESSAGE = (
    "Cannot add unique attempt constraint: duplicate "
    "(exam_id, student_id, attempt_number) rows already exist in "
    "t_exam_session"
)
DUPLICATE_IN_PROGRESS_ERROR_MESSAGE = (
    "Cannot add single in-progress constraint: multiple in_progress sessions "
    "already exist for the same (exam_id, student_id) in t_exam_session"
)


def _has_duplicate_attempt_rows() -> bool:
    bind = op.get_bind()
    duplicate_attempt_query = sa.text(
        """
        SELECT 1
        FROM t_exam_session
        GROUP BY exam_id, student_id, attempt_number
        HAVING COUNT(*) > 1
        LIMIT 1
        """
    )
    return bind.execute(duplicate_attempt_query).first() is not None


def _has_multiple_in_progress_rows() -> bool:
    bind = op.get_bind()
    duplicate_in_progress_query = sa.text(
        """
        SELECT 1
        FROM t_exam_session
        WHERE status = 'in_progress'
        GROUP BY exam_id, student_id
        HAVING COUNT(*) > 1
        LIMIT 1
        """
    )
    return bind.execute(duplicate_in_progress_query).first() is not None


def upgrade() -> None:
    if _has_duplicate_attempt_rows():
        raise RuntimeError(DUPLICATE_ATTEMPT_ERROR_MESSAGE)
    if _has_multiple_in_progress_rows():
        raise RuntimeError(DUPLICATE_IN_PROGRESS_ERROR_MESSAGE)

    op.create_unique_constraint(
        UNIQUE_ATTEMPT_CONSTRAINT_NAME,
        "t_exam_session",
        ["exam_id", "student_id", "attempt_number"],
    )
    op.create_index(
        SINGLE_IN_PROGRESS_INDEX_NAME,
        "t_exam_session",
        ["exam_id", "student_id"],
        unique=True,
        postgresql_where=sa.text("status = 'in_progress'"),
    )


def downgrade() -> None:
    op.drop_index(
        SINGLE_IN_PROGRESS_INDEX_NAME,
        table_name="t_exam_session",
    )
    op.drop_constraint(
        UNIQUE_ATTEMPT_CONSTRAINT_NAME,
        "t_exam_session",
        type_="unique",
    )
