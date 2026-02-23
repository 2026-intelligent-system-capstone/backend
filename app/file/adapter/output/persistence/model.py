from sqlalchemy import String, Boolean, Enum, BigInteger
from sqlalchemy.orm import Mapped, mapped_column
from core.db.mixins import Base
from core.db.mixins import Base, TimestampMixin, OptimisticLockMixin
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from app.file.domain.entity.file import FileStatus

class FileModel(Base, TimestampMixin, OptimisticLockMixin):
    __tablename__ = "files"

    id: Mapped[PG_UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True)
    file_name: Mapped[str] = mapped_column(String(255), nullable=False)
    file_path: Mapped[str] = mapped_column(String(512), nullable=False)
    file_extension: Mapped[str] = mapped_column(String(10), nullable=False)
    file_size: Mapped[int] = mapped_column(BigInteger, nullable=False)
    mime_type: Mapped[str] = mapped_column(String(100), nullable=False)
    status: Mapped[FileStatus] = mapped_column(
        Enum(FileStatus), default=FileStatus.PENDING, nullable=False
    )
