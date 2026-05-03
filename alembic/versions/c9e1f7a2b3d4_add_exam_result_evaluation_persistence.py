"""add exam result evaluation persistence

Revision ID: c9e1f7a2b3d4
Revises: b4d6e8f0a1c2
Create Date: 2026-04-13 22:20:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "c9e1f7a2b3d4"
down_revision = "b4d6e8f0a1c2"
branch_labels = None
depends_on = None

ASYNC_JOB_TYPES = (
    "material_ingest",
    "exam_question_generation",
    "exam_result_evaluation",
)


def _build_check_constraint(
    column_name: str, values: tuple[str, ...]
) -> sa.CheckConstraint:
    quoted = ", ".join(f"'{value}'" for value in values)
    return sa.CheckConstraint(
        f"{column_name} IN ({quoted})",
        name=f"ck_{column_name}",
    )


def upgrade() -> None:
    op.alter_column(
        "t_exam_result",
        "overall_score",
        existing_type=sa.Integer(),
        type_=sa.Float(),
        existing_nullable=True,
        postgresql_using="overall_score::double precision",
    )
    op.add_column(
        "t_exam_result",
        sa.Column(
            "strengths",
            sa.JSON(),
            nullable=False,
            server_default=sa.text("'[]'::json"),
        ),
    )
    op.add_column(
        "t_exam_result",
        sa.Column(
            "weaknesses",
            sa.JSON(),
            nullable=False,
            server_default=sa.text("'[]'::json"),
        ),
    )
    op.add_column(
        "t_exam_result",
        sa.Column(
            "improvement_suggestions",
            sa.JSON(),
            nullable=False,
            server_default=sa.text("'[]'::json"),
        ),
    )
    op.create_table(
        "t_exam_result_criterion",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("result_id", sa.UUID(), nullable=False),
        sa.Column("criterion_id", sa.UUID(), nullable=False),
        sa.Column("score", sa.Float(), nullable=True),
        sa.Column("feedback", sa.String(length=2000), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("version_id", sa.BigInteger(), nullable=False),
        sa.ForeignKeyConstraint(
            ["criterion_id"], ["t_exam_criterion.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["result_id"], ["t_exam_result.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "result_id",
            "criterion_id",
            name="uq_t_exam_result_criterion_result_id_criterion_id",
        ),
    )
    op.create_index(
        "ix_t_exam_result_criterion_result_id",
        "t_exam_result_criterion",
        ["result_id"],
        unique=False,
    )
    op.create_index(
        "ix_t_exam_result_criterion_criterion_id",
        "t_exam_result_criterion",
        ["criterion_id"],
        unique=False,
    )
    op.drop_constraint("ck_t_async_job_job_type", "t_async_job", type_="check")
    op.create_check_constraint(
        "ck_t_async_job_job_type",
        "t_async_job",
        condition=str(
            _build_check_constraint("job_type", ASYNC_JOB_TYPES).sqltext
        ),
    )


def downgrade() -> None:
    op.execute(
        sa.text(
            "DELETE FROM t_async_job WHERE job_type = 'exam_result_evaluation'"
        )
    )
    op.drop_constraint("ck_t_async_job_job_type", "t_async_job", type_="check")
    op.create_check_constraint(
        "ck_t_async_job_job_type",
        "t_async_job",
        condition=str(
            _build_check_constraint(
                "job_type",
                ("material_ingest", "exam_question_generation"),
            ).sqltext
        ),
    )
    op.drop_index(
        "ix_t_exam_result_criterion_criterion_id",
        table_name="t_exam_result_criterion",
    )
    op.drop_index(
        "ix_t_exam_result_criterion_result_id",
        table_name="t_exam_result_criterion",
    )
    op.drop_table("t_exam_result_criterion")
    op.drop_column("t_exam_result", "improvement_suggestions")
    op.drop_column("t_exam_result", "weaknesses")
    op.drop_column("t_exam_result", "strengths")
    op.alter_column(
        "t_exam_result",
        "overall_score",
        existing_type=sa.Float(),
        type_=sa.Integer(),
        existing_nullable=True,
        postgresql_using="round(overall_score)::integer",
    )
