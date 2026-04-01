from abc import ABC, abstractmethod
from collections.abc import Sequence
from uuid import UUID

from app.auth.domain.entity import CurrentUser
from app.exam.domain.command import (
    CompleteExamSessionCommand,
    CreateExamCommand,
    CreateExamQuestionCommand,
    FinalizeExamResultCommand,
    GenerateExamQuestionsCommand,
    RecordExamTurnCommand,
    UpdateExamQuestionCommand,
)
from app.exam.domain.entity import (
    Exam,
    ExamQuestion,
    ExamResult,
    ExamSession,
    ExamTurn,
    StartedExamSession,
)


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
    async def create_exam_question(
        self,
        *,
        classroom_id: UUID,
        exam_id: UUID,
        current_user: CurrentUser,
        command: CreateExamQuestionCommand,
    ) -> ExamQuestion:
        """Create exam question."""

    @abstractmethod
    async def update_exam_question(
        self,
        *,
        classroom_id: UUID,
        exam_id: UUID,
        question_id: UUID,
        current_user: CurrentUser,
        command: UpdateExamQuestionCommand,
    ) -> ExamQuestion:
        """Update exam question."""

    @abstractmethod
    async def delete_exam_question(
        self,
        *,
        classroom_id: UUID,
        exam_id: UUID,
        question_id: UUID,
        current_user: CurrentUser,
    ) -> ExamQuestion:
        """Delete exam question."""

    @abstractmethod
    async def generate_exam_questions(
        self,
        *,
        classroom_id: UUID,
        exam_id: UUID,
        current_user: CurrentUser,
        command: GenerateExamQuestionsCommand,
    ) -> Sequence[ExamQuestion]:
        """Generate and persist draft exam questions."""

    @abstractmethod
    async def start_exam_session(
        self,
        *,
        exam_id: UUID,
        current_user: CurrentUser,
    ) -> StartedExamSession:
        """Start realtime exam session."""

    @abstractmethod
    async def list_my_exam_results(
        self,
        *,
        exam_id: UUID,
        current_user: CurrentUser,
    ) -> Sequence[ExamResult]:
        """List current student's exam results."""

    @abstractmethod
    async def record_exam_turn(
        self,
        *,
        exam_id: UUID,
        session_id: UUID,
        current_user: CurrentUser,
        command: RecordExamTurnCommand,
    ) -> ExamTurn:
        """Persist one exam conversation turn."""

    @abstractmethod
    async def complete_exam_session(
        self,
        *,
        exam_id: UUID,
        session_id: UUID,
        current_user: CurrentUser,
        command: CompleteExamSessionCommand,
    ) -> ExamSession:
        """Mark student's exam session as completed."""

    @abstractmethod
    async def finalize_exam_result(
        self,
        *,
        exam_id: UUID,
        session_id: UUID,
        current_user: CurrentUser,
        command: FinalizeExamResultCommand,
    ) -> ExamResult:
        """Finalize one exam result after session completion."""
