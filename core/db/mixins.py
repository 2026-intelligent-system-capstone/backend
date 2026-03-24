from datetime import datetime

from sqlalchemy import DateTime, Integer, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """Base class for SQLAlchemy models."""

    pass


class TimestampMixin:
    """Mixin to add created_at and updated_at columns."""

    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=func.now(), onupdate=func.now(), nullable=False)


class OptimisticLockMixin:
    """Mixin for optimistic locking using a version column."""

    version_id: Mapped[int] = mapped_column(Integer, default=1, nullable=False)

    __mapper_args__ = {"version_id_col": version_id}
