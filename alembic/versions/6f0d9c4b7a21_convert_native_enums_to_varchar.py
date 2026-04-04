"""convert native enums to varchar

Revision ID: 6f0d9c4b7a21
Revises: 43fe4a9d465b
Create Date: 2026-04-02 00:00:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision = "6f0d9c4b7a21"
down_revision = "43fe4a9d465b"
branch_labels = None
depends_on = None

FILE_STATUS_ENUM = postgresql.ENUM(
    "PENDING",
    "ACTIVE",
    "DELETED",
    name="filestatus",
    create_type=False,
)
USER_STATUS_ENUM = postgresql.ENUM(
    "ACTIVE",
    "PENDING",
    "BLOCKED",
    name="userstatus",
    create_type=False,
)
USER_ROLE_ENUM = postgresql.ENUM(
    "STUDENT",
    "PROFESSOR",
    "ADMIN",
    name="userrole",
    create_type=False,
)
ORGANIZATION_AUTH_PROVIDER_ENUM = postgresql.ENUM(
    "HANSUNG_SIS",
    name="organizationauthprovider",
    create_type=False,
)


def upgrade() -> None:
    op.alter_column(
        "t_file",
        "status",
        existing_type=FILE_STATUS_ENUM,
        type_=sa.String(length=50),
        postgresql_using="lower(status::text)",
        existing_nullable=False,
    )
    op.alter_column(
        "t_user",
        "status",
        existing_type=USER_STATUS_ENUM,
        type_=sa.String(length=50),
        postgresql_using="lower(status::text)",
        existing_nullable=False,
    )
    op.alter_column(
        "t_user",
        "role",
        existing_type=USER_ROLE_ENUM,
        type_=sa.String(length=50),
        postgresql_using="lower(role::text)",
        existing_nullable=False,
    )
    op.alter_column(
        "t_organization",
        "auth_provider",
        existing_type=ORGANIZATION_AUTH_PROVIDER_ENUM,
        type_=sa.String(length=50),
        postgresql_using="lower(auth_provider::text)",
        existing_nullable=False,
    )

    FILE_STATUS_ENUM.drop(op.get_bind(), checkfirst=True)
    USER_STATUS_ENUM.drop(op.get_bind(), checkfirst=True)
    USER_ROLE_ENUM.drop(op.get_bind(), checkfirst=True)
    ORGANIZATION_AUTH_PROVIDER_ENUM.drop(op.get_bind(), checkfirst=True)


def downgrade() -> None:
    FILE_STATUS_ENUM.create(op.get_bind(), checkfirst=True)
    USER_STATUS_ENUM.create(op.get_bind(), checkfirst=True)
    USER_ROLE_ENUM.create(op.get_bind(), checkfirst=True)
    ORGANIZATION_AUTH_PROVIDER_ENUM.create(op.get_bind(), checkfirst=True)

    op.alter_column(
        "t_file",
        "status",
        existing_type=sa.String(length=50),
        type_=FILE_STATUS_ENUM,
        postgresql_using="upper(status)::filestatus",
        existing_nullable=False,
    )
    op.alter_column(
        "t_user",
        "status",
        existing_type=sa.String(length=50),
        type_=USER_STATUS_ENUM,
        postgresql_using="upper(status)::userstatus",
        existing_nullable=False,
    )
    op.alter_column(
        "t_user",
        "role",
        existing_type=sa.String(length=50),
        type_=USER_ROLE_ENUM,
        postgresql_using="upper(role)::userrole",
        existing_nullable=False,
    )
    op.alter_column(
        "t_organization",
        "auth_provider",
        existing_type=sa.String(length=50),
        type_=ORGANIZATION_AUTH_PROVIDER_ENUM,
        postgresql_using="upper(auth_provider)::organizationauthprovider",
        existing_nullable=False,
    )
