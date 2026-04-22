from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import select, text
from sqlalchemy.orm import selectinload

from app.exam.domain.entity import Exam, ExamResult, ExamSession, ExamTurn
from app.exam.domain.repository import (
    ExamRepository,
    ExamResultRepository,
    ExamSessionRepository,
    ExamTurnRepository,
)
from core.db.session import session
from core.db.sqlalchemy.models.exam import (
    exam_result_table,
    exam_session_table,
    exam_table,
    exam_turn_table,
)

ADVISORY_LOCK_SQL = "SELECT pg_advisory_xact_lock(hashtext(:lock_key))"


class ExamSQLAlchemyRepository(ExamRepository):
    async def save(self, entity: Exam) -> None:
        session.add(entity)

    async def get_by_id(self, entity_id: UUID) -> Exam | None:
        query = (
            select(Exam)
            .options(selectinload("*"))
            .where(exam_table.c.id == entity_id)
        )
        result = await session.execute(query)
        return result.scalar_one_or_none()

    async def list(self) -> Sequence[Exam]:
        query = (
            select(Exam)
            .options(selectinload("*"))
            .order_by(exam_table.c.created_at.desc())
        )
        result = await session.execute(query)
        return list(result.scalars().all())

    async def list_by_classroom(self, classroom_id: UUID) -> Sequence[Exam]:
        query = (
            select(Exam)
            .options(selectinload("*"))
            .where(exam_table.c.classroom_id == classroom_id)
            .order_by(exam_table.c.created_at.desc())
        )
        result = await session.execute(query)
        return list(result.scalars().all())


class ExamSessionSQLAlchemyRepository(ExamSessionRepository):
    async def save(self, entity: ExamSession) -> None:
        session.add(entity)

    async def get_by_id(self, entity_id: UUID) -> ExamSession | None:
        query = select(ExamSession).where(exam_session_table.c.id == entity_id)
        result = await session.execute(query)
        return result.scalar_one_or_none()

    async def list(self) -> Sequence[ExamSession]:
        query = select(ExamSession).order_by(
            exam_session_table.c.created_at.desc()
        )
        result = await session.execute(query)
        return list(result.scalars().all())

    async def list_by_exam_and_student(
        self,
        *,
        exam_id: UUID,
        student_id: UUID,
    ) -> Sequence[ExamSession]:
        query = (
            select(ExamSession)
            .where(
                exam_session_table.c.exam_id == exam_id,
                exam_session_table.c.student_id == student_id,
            )
            .order_by(exam_session_table.c.created_at.desc())
        )
        result = await session.execute(query)
        return list(result.scalars().all())

    async def list_by_exam_and_student_for_update(
        self,
        *,
        exam_id: UUID,
        student_id: UUID,
    ) -> Sequence[ExamSession]:
        await session.execute(
            text(ADVISORY_LOCK_SQL),
            {
                "lock_key": f"exam-session:{exam_id}:{student_id}",
            },
        )
        return await self.list_by_exam_and_student(
            exam_id=exam_id,
            student_id=student_id,
        )


class ExamResultSQLAlchemyRepository(ExamResultRepository):
    async def save(self, entity: ExamResult) -> None:
        session.add(entity)

    async def get_by_id(self, entity_id: UUID) -> ExamResult | None:
        query = (
            select(ExamResult)
            .options(selectinload("*"))
            .where(exam_result_table.c.id == entity_id)
        )
        result = await session.execute(query)
        return result.scalar_one_or_none()

    async def list(self) -> Sequence[ExamResult]:
        query = (
            select(ExamResult)
            .options(selectinload("*"))
            .order_by(exam_result_table.c.created_at.desc())
        )
        result = await session.execute(query)
        return list(result.scalars().all())

    async def list_by_exam_and_student(
        self,
        *,
        exam_id: UUID,
        student_id: UUID,
    ) -> Sequence[ExamResult]:
        query = (
            select(ExamResult)
            .options(selectinload("*"))
            .where(
                exam_result_table.c.exam_id == exam_id,
                exam_result_table.c.student_id == student_id,
            )
            .order_by(exam_result_table.c.created_at.desc())
        )
        result = await session.execute(query)
        return list(result.scalars().all())

    async def list_by_exam_and_student_for_update(
        self,
        *,
        exam_id: UUID,
        student_id: UUID,
    ) -> Sequence[ExamResult]:
        await session.execute(
            text(ADVISORY_LOCK_SQL),
            {
                "lock_key": f"exam-result:{exam_id}:{student_id}",
            },
        )
        return await self.list_by_exam_and_student(
            exam_id=exam_id,
            student_id=student_id,
        )


class ExamTurnSQLAlchemyRepository(ExamTurnRepository):
    async def save(self, entity: ExamTurn) -> None:
        session.add(entity)

    async def get_by_id(self, entity_id: UUID) -> ExamTurn | None:
        query = select(ExamTurn).where(exam_turn_table.c.id == entity_id)
        result = await session.execute(query)
        return result.scalar_one_or_none()

    async def list(self) -> Sequence[ExamTurn]:
        query = select(ExamTurn).order_by(exam_turn_table.c.created_at.asc())
        result = await session.execute(query)
        return list(result.scalars().all())

    async def list_by_session(
        self,
        *,
        session_id: UUID,
    ) -> Sequence[ExamTurn]:
        query = (
            select(ExamTurn)
            .where(exam_turn_table.c.session_id == session_id)
            .order_by(exam_turn_table.c.sequence.asc())
        )
        result = await session.execute(query)
        return list(result.scalars().all())
