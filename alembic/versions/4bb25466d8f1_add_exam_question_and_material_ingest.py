"""add exam question and material ingest

Revision ID: 4bb25466d8f1
Revises: 90bbf2f8d613
Create Date: 2026-04-01 18:30:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "4bb25466d8f1"
down_revision = "90bbf2f8d613"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "t_classroom_material",
        sa.Column(
            "ingest_status",
            sa.String(length=50),
            nullable=False,
            server_default="pending",
        ),
    )
    op.add_column(
        "t_classroom_material",
        sa.Column(
            "scope_candidates",
            sa.JSON(),
            nullable=False,
            server_default=sa.text("'[]'"),
        ),
    )
    op.add_column(
        "t_classroom_material",
        sa.Column("ingest_error", sa.String(length=1000), nullable=True),
    )
    op.alter_column(
        "t_classroom_material",
        "ingest_status",
        server_default=None,
    )
    op.alter_column(
        "t_classroom_material",
        "scope_candidates",
        server_default=None,
    )

    op.create_table(
        "t_exam_question",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("exam_id", sa.UUID(), nullable=False),
        sa.Column("question_number", sa.Integer(), nullable=False),
        sa.Column("bloom_level", sa.String(length=50), nullable=False),
        sa.Column("difficulty", sa.String(length=50), nullable=False),
        sa.Column("question_text", sa.String(length=5000), nullable=False),
        sa.Column("scope_text", sa.String(length=1000), nullable=False),
        sa.Column(
            "evaluation_objective",
            sa.String(length=2000),
            nullable=False,
        ),
        sa.Column("answer_key", sa.String(length=5000), nullable=False),
        sa.Column(
            "scoring_criteria",
            sa.String(length=5000),
            nullable=False,
        ),
        sa.Column("source_material_ids", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("version_id", sa.BigInteger(), nullable=False),
        sa.ForeignKeyConstraint(["exam_id"], ["t_exam.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("t_exam_question")
    op.drop_column("t_classroom_material", "ingest_error")
    op.drop_column("t_classroom_material", "scope_candidates")
    op.drop_column("t_classroom_material", "ingest_status")
