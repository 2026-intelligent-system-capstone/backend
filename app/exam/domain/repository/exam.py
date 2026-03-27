from abc import abstractmethod
from collections.abc import Sequence
from uuid import UUID

from app.exam.domain.entity import Exam, ExamResult, ExamSession
from core.repository.base import BaseRepository


class ExamRepository(BaseRepository[Exam]):
    @abstractmethod
    async def list_by_classroom(self, classroom_id: UUID) -> Sequence[Exam]:
        pass


class ExamSessionRepository(BaseRepository[ExamSession]):
    @abstractmethod
    async def list_by_exam_and_student(
        self,
        *,
        exam_id: UUID,
        student_id: UUID,
    ) -> Sequence[ExamSession]:
        pass


class ExamResultRepository(BaseRepository[ExamResult]):
    @abstractmethod
    async def list_by_exam_and_student(
        self,
        *,
        exam_id: UUID,
        student_id: UUID,
    ) -> Sequence[ExamResult]:
        pass
