from sqlalchemy import Column, ForeignKey, Integer, JSON, String
from sqlalchemy.dialects.postgresql import UUID as PG_UUID

from core.db.sqlalchemy.models.base import BaseTable, metadata

classroom_material_table = BaseTable(
    "t_classroom_material",
    metadata,
    Column("id", PG_UUID(as_uuid=True), primary_key=True),
    Column(
        "classroom_id",
        PG_UUID(as_uuid=True),
        ForeignKey("t_classroom.id", ondelete="CASCADE"),
        nullable=False,
    ),
    Column(
        "file_id",
        PG_UUID(as_uuid=True),
        ForeignKey("t_file.id", ondelete="RESTRICT"),
        nullable=False,
    ),
    Column("title", String(200), nullable=False),
    Column("week", Integer, nullable=False),
    Column("description", String(1000), nullable=True),
    Column("ingest_status", String(50), nullable=False),
    Column("scope_candidates", JSON, nullable=False, default=list),
    Column("ingest_error", String(1000), nullable=True),
    Column(
        "uploaded_by",
        PG_UUID(as_uuid=True),
        ForeignKey("t_user.id", ondelete="RESTRICT"),
        nullable=False,
    ),
)
