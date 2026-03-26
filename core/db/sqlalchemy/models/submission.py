from sqlalchemy import Column, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID as PG_UUID

from core.db.sqlalchemy.models.base import BaseTable, metadata

submission_table = BaseTable(
    "t_submission",
    metadata,
    Column("id", PG_UUID(as_uuid=True), primary_key=True),
    Column(
        "exam_id",
        PG_UUID(as_uuid=True),
        ForeignKey("t_exam.id", ondelete="CASCADE"),
        nullable=False,
    ),
    Column(
        "student_id",
        PG_UUID(as_uuid=True),
        ForeignKey("t_user.id", ondelete="RESTRICT"),
        nullable=False,
    ),
    Column("answer_text", String(10000), nullable=False),
    Column("status", String(50), nullable=False),
)
