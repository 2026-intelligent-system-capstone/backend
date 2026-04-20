from sqlalchemy import JSON, Boolean, Column, Enum, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import UUID as PG_UUID

from app.classroom.domain.entity.classroom_material import (
    ClassroomMaterialIngestStatus,
    ClassroomMaterialSourceKind,
)
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
        nullable=True,
    ),
    Column(
        "source_kind",
        Enum(
            ClassroomMaterialSourceKind,
            native_enum=False,
            values_callable=lambda enum_cls: [
                member.value for member in enum_cls
            ],
            validate_strings=True,
            length=50,
        ),
        nullable=False,
        default=ClassroomMaterialSourceKind.FILE,
    ),
    Column("source_url", String(2000), nullable=True),
    Column("title", String(200), nullable=False),
    Column("week", Integer, nullable=False),
    Column("description", String(1000), nullable=True),
    Column("original_file_name", String(255), nullable=True),
    Column("original_file_path", String(512), nullable=True),
    Column("original_file_extension", String(50), nullable=True),
    Column("original_file_size", Integer, nullable=True),
    Column("original_file_mime_type", String(100), nullable=True),
    Column("ingest_capability", JSON, nullable=False, default=dict),
    Column("ingest_metadata", JSON, nullable=False, default=dict),
    Column(
        "ingest_status",
        Enum(
            ClassroomMaterialIngestStatus,
            native_enum=False,
            values_callable=lambda enum_cls: [
                member.value for member in enum_cls
            ],
            validate_strings=True,
            length=50,
        ),
        nullable=False,
        default=ClassroomMaterialIngestStatus.PENDING,
    ),
    Column("scope_candidates", JSON, nullable=False, default=list),
    Column("ingest_error", String(1000), nullable=True),
    Column(
        "uploaded_by",
        PG_UUID(as_uuid=True),
        ForeignKey("t_user.id", ondelete="RESTRICT"),
        nullable=False,
    ),
)
