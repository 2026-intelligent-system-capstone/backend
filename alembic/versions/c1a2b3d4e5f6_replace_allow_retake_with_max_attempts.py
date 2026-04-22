"""replace allow_retake with max_attempts

Revision ID: c1a2b3d4e5f6
Revises: b7d5e6a1c2f4
Create Date: 2026-04-07 14:30:00.000000

NOTE:
- allow_retake=true legacy data is backfilled to max_attempts=2 by policy
  decision.
- This migration is intentionally not reversible because boolean allow_retake
  cannot faithfully restore max_attempts values greater than 2.
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision = "c1a2b3d4e5f6"
down_revision = "b7d5e6a1c2f4"
branch_labels = None
depends_on = None


TEMPORARY_MAX_ATTEMPTS_DEFAULT = 1
MAX_ATTEMPTS_FROM_ALLOW_RETAKE_TRUE = 2


def _column_names(table_name: str) -> set[str]:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return {column["name"] for column in inspector.get_columns(table_name)}


def upgrade() -> None:
    column_names = _column_names("t_exam")

    if "max_attempts" not in column_names:
        op.add_column(
            "t_exam",
            sa.Column(
                "max_attempts",
                sa.Integer(),
                nullable=True,
                server_default=sa.text(str(TEMPORARY_MAX_ATTEMPTS_DEFAULT)),
            ),
        )

    if "allow_retake" in column_names:
        op.execute(
            sa.text(
                """
                UPDATE t_exam
                SET max_attempts = CASE
                    WHEN allow_retake IS TRUE THEN :retake_allowed_value
                    ELSE :default_value
                END
                """
            ).bindparams(
                retake_allowed_value=MAX_ATTEMPTS_FROM_ALLOW_RETAKE_TRUE,
                default_value=TEMPORARY_MAX_ATTEMPTS_DEFAULT,
            )
        )
        op.drop_column("t_exam", "allow_retake")
    else:
        op.execute(
            sa.text(
                "UPDATE t_exam "
                "SET max_attempts = :value "
                "WHERE max_attempts IS NULL"
            ).bindparams(value=TEMPORARY_MAX_ATTEMPTS_DEFAULT)
        )

    op.alter_column(
        "t_exam",
        "max_attempts",
        existing_type=sa.Integer(),
        nullable=False,
        server_default=None,
    )


def downgrade() -> None:
    raise RuntimeError(
        "c1a2b3d4e5f6 downgrade is not supported because allow_retake "
        "cannot faithfully restore max_attempts values"
    )
