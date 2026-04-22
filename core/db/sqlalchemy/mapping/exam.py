from sqlalchemy.orm import relationship

from app.exam.domain.entity import (
    Exam,
    ExamCriterion,
    ExamQuestion,
    ExamResult,
    ExamResultCriterion,
    ExamSession,
    ExamTurn,
)
from core.db.sqlalchemy.models.exam import (
    exam_criterion_table,
    exam_question_table,
    exam_result_criterion_table,
    exam_result_table,
    exam_session_table,
    exam_table,
    exam_turn_table,
)

from .base import mapper_registry


def init_exam_mappers():
    mapper_registry.map_imperatively(ExamCriterion, exam_criterion_table)
    mapper_registry.map_imperatively(ExamQuestion, exam_question_table)
    mapper_registry.map_imperatively(
        Exam,
        exam_table,
        properties={
            "criteria": relationship(
                ExamCriterion,
                cascade="all, delete-orphan",
                order_by=exam_criterion_table.c.sort_order,
            ),
            "questions": relationship(
                ExamQuestion,
                cascade="all, delete-orphan",
                order_by=exam_question_table.c.question_number,
            ),
        },
        version_id_col=exam_table.c.version_id,
    )
    mapper_registry.map_imperatively(
        ExamSession,
        exam_session_table,
        version_id_col=exam_session_table.c.version_id,
    )
    mapper_registry.map_imperatively(
        ExamResultCriterion,
        exam_result_criterion_table,
        version_id_col=exam_result_criterion_table.c.version_id,
    )
    mapper_registry.map_imperatively(
        ExamResult,
        exam_result_table,
        properties={
            "criteria_results": relationship(
                ExamResultCriterion,
                cascade="all, delete-orphan",
                order_by=exam_result_criterion_table.c.created_at.asc(),
            ),
        },
        version_id_col=exam_result_table.c.version_id,
    )
    mapper_registry.map_imperatively(
        ExamTurn,
        exam_turn_table,
        version_id_col=exam_turn_table.c.version_id,
    )
