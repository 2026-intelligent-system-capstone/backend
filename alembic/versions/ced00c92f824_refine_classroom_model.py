"""refine classroom model

Revision ID: ced00c92f824
Revises: a2d651fa6123
Create Date: 2026-03-24 21:19:59.831282
"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision = "ced00c92f824"
down_revision = "a2d651fa6123"
branch_labels = None
depends_on = None


CLASSROOM_UNIQUE_CONSTRAINT = (
    "uq_classroom_organization_name_grade_semester_section"
)


def upgrade() -> None:
    op.add_column(
        "t_classroom",
        sa.Column("professor_ids", postgresql.ARRAY(sa.UUID()), nullable=True),
    )
    op.add_column(
        "t_classroom",
        sa.Column("grade", sa.Integer(), nullable=True),
    )
    op.add_column(
        "t_classroom",
        sa.Column("semester", sa.String(length=20), nullable=True),
    )
    op.add_column(
        "t_classroom",
        sa.Column("student_ids", postgresql.ARRAY(sa.UUID()), nullable=True),
    )

    op.execute(
        sa.text(
            """
            UPDATE t_classroom
            SET professor_ids = ARRAY[instructor_id],
                grade = 1,
                semester = term,
                student_ids = ARRAY[]::uuid[],
                section = COALESCE(section, '01')
            """
        )
    )

    op.alter_column(
        "t_classroom",
        "professor_ids",
        existing_type=postgresql.ARRAY(sa.UUID()),
        nullable=False,
    )
    op.alter_column(
        "t_classroom",
        "grade",
        existing_type=sa.Integer(),
        nullable=False,
    )
    op.alter_column(
        "t_classroom",
        "semester",
        existing_type=sa.String(length=20),
        nullable=False,
    )
    op.alter_column(
        "t_classroom",
        "student_ids",
        existing_type=postgresql.ARRAY(sa.UUID()),
        nullable=False,
    )
    op.alter_column(
        "t_classroom",
        "section",
        existing_type=sa.VARCHAR(length=50),
        nullable=False,
    )
    op.drop_constraint(
        op.f("t_classroom_organization_id_code_key"),
        "t_classroom",
        type_="unique",
    )
    op.create_unique_constraint(
        CLASSROOM_UNIQUE_CONSTRAINT,
        "t_classroom",
        ["organization_id", "name", "grade", "semester", "section"],
    )
    op.drop_constraint(
        op.f("t_classroom_instructor_id_fkey"),
        "t_classroom",
        type_="foreignkey",
    )
    op.drop_column("t_classroom", "term")
    op.drop_column("t_classroom", "is_active")
    op.drop_column("t_classroom", "instructor_id")
    op.drop_column("t_classroom", "code")


def downgrade() -> None:
    op.add_column(
        "t_classroom",
        sa.Column("code", sa.VARCHAR(length=50), nullable=True),
    )
    op.add_column(
        "t_classroom",
        sa.Column("instructor_id", sa.UUID(), nullable=True),
    )
    op.add_column(
        "t_classroom",
        sa.Column("is_active", sa.BOOLEAN(), nullable=True),
    )
    op.add_column(
        "t_classroom",
        sa.Column("term", sa.VARCHAR(length=50), nullable=True),
    )

    op.execute(
        sa.text(
            """
            UPDATE t_classroom
            SET code = LOWER(REPLACE(name, ' ', '-')) || '-' || section,
                instructor_id = professor_ids[1],
                is_active = true,
                term = semester
            """
        )
    )

    op.alter_column(
        "t_classroom",
        "code",
        existing_type=sa.VARCHAR(length=50),
        nullable=False,
    )
    op.alter_column(
        "t_classroom",
        "instructor_id",
        existing_type=sa.UUID(),
        nullable=False,
    )
    op.alter_column(
        "t_classroom",
        "is_active",
        existing_type=sa.BOOLEAN(),
        nullable=False,
    )
    op.alter_column(
        "t_classroom",
        "term",
        existing_type=sa.VARCHAR(length=50),
        nullable=False,
    )
    op.create_foreign_key(
        op.f("t_classroom_instructor_id_fkey"),
        "t_classroom",
        "t_user",
        ["instructor_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.drop_constraint(
        CLASSROOM_UNIQUE_CONSTRAINT,
        "t_classroom",
        type_="unique",
    )
    op.create_unique_constraint(
        op.f("t_classroom_organization_id_code_key"),
        "t_classroom",
        ["organization_id", "code"],
    )
    op.alter_column(
        "t_classroom",
        "section",
        existing_type=sa.VARCHAR(length=50),
        nullable=True,
    )
    op.drop_column("t_classroom", "student_ids")
    op.drop_column("t_classroom", "semester")
    op.drop_column("t_classroom", "grade")
    op.drop_column("t_classroom", "professor_ids")
