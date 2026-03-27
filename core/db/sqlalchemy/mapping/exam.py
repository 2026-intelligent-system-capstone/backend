from sqlalchemy.orm import relationship

from app.exam.domain.entity import Exam, ExamCriterion, ExamResult, ExamSession
from core.db.sqlalchemy.models.exam import (
    exam_criterion_table,
    exam_result_table,
    exam_session_table,
    exam_table,
)

from .base import mapper_registry


def init_exam_mappers():
    mapper_registry.map_imperatively(ExamCriterion, exam_criterion_table)
    mapper_registry.map_imperatively(
        Exam,
        exam_table,
        properties={
            "criteria": relationship(
                ExamCriterion,
                cascade="all, delete-orphan",
                order_by=exam_criterion_table.c.sort_order,
            )
        },
        version_id_col=exam_table.c.version_id,
    )
    mapper_registry.map_imperatively(
        ExamSession,
        exam_session_table,
        version_id_col=exam_session_table.c.version_id,
    )
    mapper_registry.map_imperatively(
        ExamResult,
        exam_result_table,
        version_id_col=exam_result_table.c.version_id,
    )
