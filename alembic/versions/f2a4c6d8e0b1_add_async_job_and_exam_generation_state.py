"""add async job and exam generation state

Revision ID: f2a4c6d8e0b1
Revises: e1f2a3b4c5d6
Create Date: 2026-04-13 14:20:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "f2a4c6d8e0b1"
down_revision = "e1f2a3b4c5d6"
branch_labels = None
depends_on = None

ASYNC_JOB_TYPES = ("material_ingest", "exam_question_generation")
ASYNC_JOB_STATUSES = ("queued", "running", "completed", "failed")
ASYNC_JOB_TARGET_TYPES = ("classroom_material", "exam")
EXAM_GENERATION_STATUSES = ("idle", "queued", "running", "completed", "failed")


def _build_check_constraint(
    column_name: str, values: tuple[str, ...]
) -> sa.CheckConstraint:
    quoted = ", ".join(f"'{value}'" for value in values)
    return sa.CheckConstraint(
        f"{column_name} IN ({quoted})",
        name=f"ck_{column_name}",
    )


def upgrade() -> None:
    op.create_table(
        "t_async_job",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("job_type", sa.String(length=80), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("target_type", sa.String(length=80), nullable=False),
        sa.Column("target_id", sa.UUID(), nullable=False),
        sa.Column(
            "payload",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "result",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("error_message", sa.String(length=1000), nullable=True),
        sa.Column("requested_by", sa.UUID(), nullable=False),
        sa.Column("available_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "last_heartbeat_at", sa.DateTime(timezone=True), nullable=True
        ),
        sa.Column(
            "attempts",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column(
            "max_attempts",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("3"),
        ),
        sa.Column("dedupe_key", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("version_id", sa.BigInteger(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_check_constraint(
        "ck_t_async_job_job_type",
        "t_async_job",
        condition=str(
            _build_check_constraint("job_type", ASYNC_JOB_TYPES).sqltext
        ),
    )
    op.create_check_constraint(
        "ck_t_async_job_status",
        "t_async_job",
        condition=str(
            _build_check_constraint("status", ASYNC_JOB_STATUSES).sqltext
        ),
    )
    op.create_check_constraint(
        "ck_t_async_job_target_type",
        "t_async_job",
        condition=str(
            _build_check_constraint(
                "target_type", ASYNC_JOB_TARGET_TYPES
            ).sqltext
        ),
    )
    op.create_check_constraint(
        "ck_t_async_job_attempts_non_negative",
        "t_async_job",
        condition="attempts >= 0",
    )
    op.create_check_constraint(
        "ck_t_async_job_max_attempts_positive",
        "t_async_job",
        condition="max_attempts > 0",
    )
    op.create_index(
        "ix_t_async_job_status_available_at",
        "t_async_job",
        ["status", "available_at"],
        unique=False,
    )
    op.create_index(
        "ix_t_async_job_target_type_target_id",
        "t_async_job",
        ["target_type", "target_id"],
        unique=False,
    )

    op.add_column(
        "t_exam",
        sa.Column(
            "generation_status",
            sa.String(length=50),
            nullable=False,
            server_default="idle",
        ),
    )
    op.add_column(
        "t_exam",
        sa.Column("generation_error", sa.String(length=1000), nullable=True),
    )
    op.add_column(
        "t_exam",
        sa.Column("generation_job_id", sa.UUID(), nullable=True),
    )
    op.add_column(
        "t_exam",
        sa.Column(
            "generation_requested_at", sa.DateTime(timezone=True), nullable=True
        ),
    )
    op.add_column(
        "t_exam",
        sa.Column(
            "generation_completed_at", sa.DateTime(timezone=True), nullable=True
        ),
    )
    op.create_check_constraint(
        "ck_t_exam_generation_status",
        "t_exam",
        condition=str(
            _build_check_constraint(
                "generation_status", EXAM_GENERATION_STATUSES
            ).sqltext
        ),
    )


def downgrade() -> None:
    op.drop_constraint("ck_t_exam_generation_status", "t_exam", type_="check")
    op.drop_column("t_exam", "generation_completed_at")
    op.drop_column("t_exam", "generation_requested_at")
    op.drop_column("t_exam", "generation_job_id")
    op.drop_column("t_exam", "generation_error")
    op.drop_column("t_exam", "generation_status")

    op.drop_index(
        "ix_t_async_job_target_type_target_id", table_name="t_async_job"
    )
    op.drop_index(
        "ix_t_async_job_status_available_at", table_name="t_async_job"
    )
    op.drop_constraint(
        "ck_t_async_job_max_attempts_positive", "t_async_job", type_="check"
    )
    op.drop_constraint(
        "ck_t_async_job_attempts_non_negative", "t_async_job", type_="check"
    )
    op.drop_constraint(
        "ck_t_async_job_target_type", "t_async_job", type_="check"
    )
    op.drop_constraint("ck_t_async_job_status", "t_async_job", type_="check")
    op.drop_constraint("ck_t_async_job_job_type", "t_async_job", type_="check")
    op.drop_table("t_async_job")
