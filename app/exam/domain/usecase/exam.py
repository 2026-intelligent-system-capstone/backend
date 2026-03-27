from abc import ABC, abstractmethod
from collections.abc import Sequence
from uuid import UUID

from app.auth.domain.entity import CurrentUser
from app.exam.domain.command import CreateExamCommand
from app.exam.domain.entity import Exam, ExamResult, StartedExamSession


class ExamUseCase(ABC):
    @abstractmethod
    async def create_exam(
        self,
        *,
        classroom_id: UUID,
        current_user: CurrentUser,
        command: CreateExamCommand,
    ) -> Exam:
        """Create exam."""

    @abstractmethod
    async def list_exams(
        self,
        *,
        classroom_id: UUID,
        current_user: CurrentUser,
    ) -> Sequence[Exam]:
        """List exams."""

    @abstractmethod
    async def get_exam(
        self,
        *,
        classroom_id: UUID,
        exam_id: UUID,
        current_user: CurrentUser,
    ) -> Exam:
        """Get exam."""

    @abstractmethod
    async def start_exam_session(
        self,
        *,
        classroom_id: UUID,
        exam_id: UUID,
        current_user: CurrentUser,
    ) -> StartedExamSession:
        """Start realtime exam session."""

    @abstractmethod
    async def list_my_exam_results(
        self,
        *,
        classroom_id: UUID,
        exam_id: UUID,
        current_user: CurrentUser,
    ) -> Sequence[ExamResult]:
        """List current student's exam results."""
