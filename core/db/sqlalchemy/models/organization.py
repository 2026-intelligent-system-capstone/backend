from sqlalchemy import Boolean, Column, Enum, String
from sqlalchemy.dialects.postgresql import UUID as PG_UUID

from app.organization.domain.entity.organization import OrganizationAuthProvider
from core.db.sqlalchemy.models.base import BaseTable, metadata

organization_table = BaseTable(
    "t_organization",
    metadata,
    Column("id", PG_UUID(as_uuid=True), primary_key=True),
    Column("code", String(50), unique=True, nullable=False),
    Column("name", String(100), nullable=False),
    Column(
        "auth_provider",
        Enum(OrganizationAuthProvider),
        nullable=False,
    ),
    Column("is_active", Boolean, nullable=False, default=True),
)
