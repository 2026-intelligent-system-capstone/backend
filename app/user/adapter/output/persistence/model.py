from typing import Optional
from sqlalchemy import String, Boolean, Enum, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column
from core.db.mixins import Base
from core.db.mixins import TimestampMixin, OptimisticLockMixin
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from app.user.domain.entity.user import UserStatus

class UserModel(Base, TimestampMixin, OptimisticLockMixin):
    __tablename__ = "users"

    id: Mapped[PG_UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True)
    username: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    password: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    
    # Profile fields (Flattened from Profile VO)
    nickname: Mapped[str] = mapped_column(String(100), nullable=False)
    real_name: Mapped[str] = mapped_column(String(100), nullable=False)
    phone_number: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    profile_image_id: Mapped[Optional[PG_UUID]] = mapped_column(
        PG_UUID(as_uuid=True), 
        ForeignKey("files.id", ondelete="SET NULL"),
        nullable=True
    )
    
    status: Mapped[UserStatus] = mapped_column(
        Enum(UserStatus), default=UserStatus.ACTIVE, nullable=False
    )
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    
    # OAuth2 support
    oauth_provider: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    oauth_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
