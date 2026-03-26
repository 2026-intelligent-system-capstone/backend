"""add exam domain

Revision ID: 98f0d64f3f11
Revises: daf876d85767
Create Date: 2026-03-26 15:10:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "98f0d64f3f11"
down_revision = "daf876d85767"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "t_exam",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("classroom_id", sa.UUID(), nullable=False),
        sa.Column("title", sa.String(length=100), nullable=False),
        sa.Column("description", sa.String(length=1000), nullable=True),
        sa.Column("exam_type", sa.String(length=50), nullable=False),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("duration_minutes", sa.Integer(), nullable=False),
        sa.Column("starts_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ends_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("allow_retake", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("version_id", sa.BigInteger(), nullable=False),
        sa.ForeignKeyConstraint(
            ["classroom_id"], ["t_classroom.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "t_exam_criterion",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("exam_id", sa.UUID(), nullable=False),
        sa.Column("title", sa.String(length=100), nullable=False),
        sa.Column("description", sa.String(length=1000), nullable=True),
        sa.Column("weight", sa.Integer(), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.Column(
            "excellent_definition", sa.String(length=1000), nullable=True
        ),
        sa.Column("average_definition", sa.String(length=1000), nullable=True),
        sa.Column("poor_definition", sa.String(length=1000), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("version_id", sa.BigInteger(), nullable=False),
        sa.ForeignKeyConstraint(["exam_id"], ["t_exam.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "t_exam_session",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("exam_id", sa.UUID(), nullable=False),
        sa.Column("student_id", sa.UUID(), nullable=False),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "last_activity_at", sa.DateTime(timezone=True), nullable=False
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("attempt_number", sa.Integer(), nullable=False),
        sa.Column("provider_session_id", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("version_id", sa.BigInteger(), nullable=False),
        sa.ForeignKeyConstraint(["exam_id"], ["t_exam.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["student_id"], ["t_user.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "t_exam_result",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("exam_id", sa.UUID(), nullable=False),
        sa.Column("session_id", sa.UUID(), nullable=False),
        sa.Column("student_id", sa.UUID(), nullable=False),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("overall_score", sa.Integer(), nullable=True),
        sa.Column("summary", sa.String(length=2000), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("version_id", sa.BigInteger(), nullable=False),
        sa.ForeignKeyConstraint(["exam_id"], ["t_exam.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["session_id"], ["t_exam_session.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["student_id"], ["t_user.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("t_exam_result")
    op.drop_table("t_exam_session")
    op.drop_table("t_exam_criterion")
    op.drop_table("t_exam")
