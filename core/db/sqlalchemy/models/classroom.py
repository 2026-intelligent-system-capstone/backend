from sqlalchemy import (
    Boolean,
    Column,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.dialects.postgresql import UUID as PG_UUID

from core.db.sqlalchemy.models.base import BaseTable, metadata

classroom_table = BaseTable(
    "t_classroom",
    metadata,
    Column("id", PG_UUID(as_uuid=True), primary_key=True),
    Column(
        "organization_id",
        PG_UUID(as_uuid=True),
        ForeignKey("t_organization.id", ondelete="RESTRICT"),
        nullable=False,
    ),
    Column("name", String(100), nullable=False),
    Column("professor_ids", ARRAY(PG_UUID(as_uuid=True)), nullable=False),
    Column("grade", Integer, nullable=False),
    Column("semester", String(20), nullable=False),
    Column("section", String(50), nullable=False),
    Column("description", String(500), nullable=True),
    Column("student_ids", ARRAY(PG_UUID(as_uuid=True)), nullable=False),
    Column(
        "allow_student_material_access",
        Boolean,
        nullable=False,
        default=False,
    ),
    UniqueConstraint(
        "organization_id",
        "name",
        "grade",
        "semester",
        "section",
    ),
)
