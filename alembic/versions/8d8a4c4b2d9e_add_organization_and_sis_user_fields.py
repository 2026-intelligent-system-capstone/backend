"""Add organization and SIS user fields

Revision ID: 8d8a4c4b2d9e
Revises: 693ae09dc797
Create Date: 2026-03-24 00:30:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision = "8d8a4c4b2d9e"
down_revision = "693ae09dc797"
branch_labels = None
depends_on = None

HANSUNG_ORGANIZATION_ID = "11111111-1111-1111-1111-111111111111"


def upgrade() -> None:
    organization_auth_provider = sa.Enum(
        "HANSUNG_SIS",
        name="organizationauthprovider",
    )
    user_role = sa.Enum("STUDENT", "PROFESSOR", "ADMIN", name="userrole")

    organization_auth_provider.create(op.get_bind(), checkfirst=True)
    user_role.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "t_organization",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("code", sa.String(length=50), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column(
            "auth_provider",
            organization_auth_provider,
            nullable=False,
        ),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("version_id", sa.BigInteger(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code"),
    )

    op.execute(
        sa.text(
            """
            INSERT INTO t_organization (
                id,
                code,
                name,
                auth_provider,
                is_active,
                created_at,
                updated_at,
                version_id
            ) VALUES (
                :id,
                'hansung',
                'Hansung University',
                'HANSUNG_SIS',
                true,
                NOW(),
                NOW(),
                0
            )
            """
        ),
        {"id": HANSUNG_ORGANIZATION_ID},
    )

    op.add_column(
        "t_user",
        sa.Column("organization_id", sa.UUID(), nullable=True),
    )
    op.add_column(
        "t_user",
        sa.Column("login_id", sa.String(length=100), nullable=True),
    )
    op.add_column(
        "t_user",
        sa.Column("role", user_role, nullable=True),
    )
    op.alter_column(
        "t_user",
        "email",
        existing_type=sa.String(length=255),
        nullable=True,
    )
    op.alter_column(
        "t_user",
        "real_name",
        new_column_name="name",
        existing_type=sa.String(length=100),
    )

    op.execute(
        sa.text(
            """
            UPDATE t_user
            SET organization_id = :organization_id,
                login_id = username,
                role = 'STUDENT'
            WHERE organization_id IS NULL
            """
        ),
        {"organization_id": HANSUNG_ORGANIZATION_ID},
    )

    op.alter_column(
        "t_user",
        "organization_id",
        existing_type=sa.UUID(),
        nullable=False,
    )
    op.alter_column(
        "t_user",
        "login_id",
        existing_type=sa.String(length=100),
        nullable=False,
    )
    op.alter_column(
        "t_user",
        "role",
        existing_type=user_role,
        nullable=False,
    )
    op.create_foreign_key(
        "fk_user_organization_id",
        "t_user",
        "t_organization",
        ["organization_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_unique_constraint(
        "uq_user_organization_login_id",
        "t_user",
        ["organization_id", "login_id"],
    )

    op.execute(
        sa.text(
            "ALTER TABLE t_user DROP CONSTRAINT IF EXISTS t_user_username_key"
        )
    )
    op.execute(
        sa.text("ALTER TABLE t_user DROP CONSTRAINT IF EXISTS t_user_email_key")
    )
    op.drop_column("t_user", "password")
    op.drop_column("t_user", "username")


def downgrade() -> None:
    user_role = sa.Enum("STUDENT", "PROFESSOR", "ADMIN", name="userrole")
    organization_auth_provider = sa.Enum(
        "HANSUNG_SIS",
        name="organizationauthprovider",
    )

    op.add_column(
        "t_user",
        sa.Column("username", sa.String(length=50), nullable=True),
    )
    op.add_column(
        "t_user",
        sa.Column("password", sa.String(length=255), nullable=True),
    )
    op.execute(
        sa.text(
            """
            UPDATE t_user
            SET username = login_id,
                password = '__migrated_to_sis__'
            WHERE username IS NULL
            """
        )
    )
    op.alter_column(
        "t_user",
        "username",
        existing_type=sa.String(length=50),
        nullable=False,
    )
    op.alter_column(
        "t_user",
        "password",
        existing_type=sa.String(length=255),
        nullable=False,
    )
    op.create_unique_constraint("t_user_username_key", "t_user", ["username"])
    op.create_unique_constraint("t_user_email_key", "t_user", ["email"])
    op.drop_constraint(
        "uq_user_organization_login_id", "t_user", type_="unique"
    )
    op.drop_constraint("fk_user_organization_id", "t_user", type_="foreignkey")
    op.drop_column("t_user", "role")
    op.drop_column("t_user", "login_id")
    op.drop_column("t_user", "organization_id")
    op.alter_column(
        "t_user",
        "name",
        new_column_name="real_name",
        existing_type=sa.String(length=100),
    )
    op.alter_column(
        "t_user",
        "email",
        existing_type=sa.String(length=255),
        nullable=False,
    )

    op.drop_table("t_organization")
    organization_auth_provider.drop(op.get_bind(), checkfirst=True)
    user_role.drop(op.get_bind(), checkfirst=True)
