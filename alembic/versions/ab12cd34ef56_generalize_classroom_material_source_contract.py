"""generalize classroom material source contract

Revision ID: ab12cd34ef56
Revises: d4e5f6a7b8c9
Create Date: 2026-04-09 12:00:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision = "ab12cd34ef56"
down_revision = "d4e5f6a7b8c9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "t_classroom_material",
        sa.Column(
            "source_kind",
            sa.String(length=50),
            nullable=False,
            server_default="file",
        ),
    )
    op.add_column(
        "t_classroom_material",
        sa.Column("source_url", sa.String(length=2000), nullable=True),
    )
    op.add_column(
        "t_classroom_material",
        sa.Column("original_file_name", sa.String(length=255), nullable=True),
    )
    op.add_column(
        "t_classroom_material",
        sa.Column("original_file_path", sa.String(length=512), nullable=True),
    )
    op.add_column(
        "t_classroom_material",
        sa.Column(
            "original_file_extension",
            sa.String(length=50),
            nullable=True,
        ),
    )
    op.add_column(
        "t_classroom_material",
        sa.Column("original_file_size", sa.Integer(), nullable=True),
    )
    op.add_column(
        "t_classroom_material",
        sa.Column(
            "original_file_mime_type",
            sa.String(length=100),
            nullable=True,
        ),
    )
    op.add_column(
        "t_classroom_material",
        sa.Column(
            "ingest_capability",
            sa.JSON(),
            nullable=False,
            server_default=sa.text("'{\"supported\": true}'"),
        ),
    )
    op.add_column(
        "t_classroom_material",
        sa.Column(
            "ingest_metadata",
            sa.JSON(),
            nullable=False,
            server_default=sa.text("'{}'"),
        ),
    )

    op.execute(
        """
        UPDATE t_classroom_material AS material
        SET original_file_name = file.file_name,
            original_file_path = file.file_path,
            original_file_extension = file.file_extension,
            original_file_size = file.file_size,
            original_file_mime_type = file.mime_type,
            ingest_metadata = json_build_object('mime_type', file.mime_type)
        FROM t_file AS file
        WHERE file.id = material.file_id
        """
    )

    op.alter_column(
        "t_classroom_material",
        "source_kind",
        server_default=None,
    )
    op.alter_column(
        "t_classroom_material",
        "ingest_capability",
        server_default=None,
    )
    op.alter_column(
        "t_classroom_material",
        "ingest_metadata",
        server_default=None,
    )
    op.alter_column(
        "t_classroom_material",
        "file_id",
        existing_type=sa.UUID(),
        nullable=True,
    )


def downgrade() -> None:
    op.alter_column(
        "t_classroom_material",
        "file_id",
        existing_type=sa.UUID(),
        nullable=False,
    )
    op.drop_column("t_classroom_material", "ingest_metadata")
    op.drop_column("t_classroom_material", "ingest_capability")
    op.drop_column("t_classroom_material", "original_file_mime_type")
    op.drop_column("t_classroom_material", "original_file_size")
    op.drop_column("t_classroom_material", "original_file_extension")
    op.drop_column("t_classroom_material", "original_file_path")
    op.drop_column("t_classroom_material", "original_file_name")
    op.drop_column("t_classroom_material", "source_url")
    op.drop_column("t_classroom_material", "source_kind")
