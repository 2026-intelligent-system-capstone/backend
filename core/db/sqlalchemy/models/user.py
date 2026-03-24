from sqlalchemy import (
    Boolean,
    Column,
    Enum,
    ForeignKey,
    String,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID

from app.user.domain.entity.user import UserRole, UserStatus
from core.db.sqlalchemy.models.base import BaseTable, metadata

user_table = BaseTable(
    "t_user",
    metadata,
    Column("id", PG_UUID(as_uuid=True), primary_key=True),
    Column(
        "organization_id",
        PG_UUID(as_uuid=True),
        ForeignKey("t_organization.id", ondelete="RESTRICT"),
        nullable=False,
    ),
    Column("login_id", String(100), nullable=False),
    Column("email", String(255), nullable=True),
    Column("nickname", String(100), nullable=False),
    Column("name", String(100), nullable=False),
    Column("phone_number", String(20), nullable=True),
    Column(
        "profile_image_id",
        PG_UUID(as_uuid=True),
        ForeignKey("t_file.id", ondelete="SET NULL"),
        nullable=True,
    ),
    Column("role", Enum(UserRole), nullable=False),
    Column(
        "status", Enum(UserStatus), nullable=False, default=UserStatus.ACTIVE
    ),
    Column("is_deleted", Boolean, nullable=False, default=False),
    UniqueConstraint("organization_id", "login_id"),
)
