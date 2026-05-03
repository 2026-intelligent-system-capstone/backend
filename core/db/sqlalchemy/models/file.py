from sqlalchemy import BigInteger, Column, Enum, String
from sqlalchemy.dialects.postgresql import UUID as PG_UUID

from app.file.domain.entity.file import FileStatus
from core.db.sqlalchemy.models.base import BaseTable, metadata

file_table = BaseTable(
    "t_file",
    metadata,
    Column("id", PG_UUID(as_uuid=True), primary_key=True),
    Column("file_name", String(255), nullable=False),
    Column("file_path", String(512), nullable=False),
    Column("file_extension", String(10), nullable=False),
    Column("file_size", BigInteger, nullable=False),
    Column("mime_type", String(100), nullable=False),
    Column(
        "status",
        Enum(
            FileStatus,
            native_enum=False,
            values_callable=lambda enum_cls: [
                member.value for member in enum_cls
            ],
            validate_strings=True,
            length=50,
        ),
        nullable=False,
        default=FileStatus.PENDING,
    ),
)
