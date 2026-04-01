from collections.abc import Sequence
from datetime import UTC, datetime
from uuid import UUID

from app.auth.application.exception import AuthForbiddenException
from app.auth.domain.entity import CurrentUser
from app.classroom.domain.usecase import ClassroomUseCase
from app.exam.application.exception import ExamNotFoundException
from app.exam.domain.command import (
    CompleteExamSessionCommand,
    CreateExamCommand,
    FinalizeExamResultCommand,
    RecordExamTurnCommand,
)
from app.exam.domain.entity import (
    Exam,
    ExamResult,
    ExamSession,
    ExamTurn,
    StartedExamSession,
)
from app.exam.domain.repository import (
    ExamRepository,
    ExamResultRepository,
    ExamSessionRepository,
    ExamTurnRepository,
)
from app.exam.domain.service import RealtimeSessionPort
from app.exam.domain.usecase import ExamUseCase
from app.user.domain.entity import UserRole
from core.db.transactional import transactional


class ExamService(ExamUseCase):
    def __init__(
        self,
        *,
        repository: ExamRepository,
        classroom_usecase: ClassroomUseCase,
        session_repository: ExamSessionRepository,
        result_repository: ExamResultRepository,
        turn_repository: ExamTurnRepository,
        realtime_session_port: RealtimeSessionPort,
    ):
        self.repository = repository
        self.classroom_usecase = classroom_usecase
        self.session_repository = session_repository
        self.result_repository = result_repository
        self.turn_repository = turn_repository
        self.realtime_session_port = realtime_session_port

    @transactional
    async def create_exam(
        self,
        *,
        classroom_id: UUID,
        current_user: CurrentUser,
        command: CreateExamCommand,
    ) -> Exam:
        if current_user.role not in {UserRole.PROFESSOR, UserRole.ADMIN}:
            raise AuthForbiddenException()

        await self.classroom_usecase.get_classroom(
            classroom_id=classroom_id,
            current_user=current_user,
        )
        exam = Exam.create(
            classroom_id=classroom_id,
            title=command.title,
            description=command.description,
            exam_type=command.exam_type,
            duration_minutes=command.duration_minutes,
            starts_at=command.starts_at,
            ends_at=command.ends_at,
            allow_retake=command.allow_retake,
            criteria=command.criteria,
        )
        await self.repository.save(exam)
        return exam

    async def list_exams(
        self,
        *,
        classroom_id: UUID,
        current_user: CurrentUser,
    ) -> Sequence[Exam]:
        await self.classroom_usecase.get_classroom(
            classroom_id=classroom_id,
            current_user=current_user,
        )
        return await self.repository.list_by_classroom(classroom_id)

    async def get_exam(
        self,
        *,
        classroom_id: UUID,
        exam_id: UUID,
        current_user: CurrentUser,
    ) -> Exam:
        await self.classroom_usecase.get_classroom(
            classroom_id=classroom_id,
            current_user=current_user,
        )
        exam = await self.repository.get_by_id(exam_id)
        if exam is None or not exam.belongs_to_classroom(classroom_id):
            raise ExamNotFoundException()
        return exam

    @transactional
    async def start_exam_session(
        self,
        *,
        exam_id: UUID,
        current_user: CurrentUser,
    ) -> StartedExamSession:
        if current_user.role != UserRole.STUDENT:
            raise AuthForbiddenException()
        exam = await self.repository.get_by_id(exam_id)
        if exam is None:
            raise ExamNotFoundException()
        await self.classroom_usecase.get_classroom(
            classroom_id=exam.classroom_id,
            current_user=current_user,
        )
        secret = await self.realtime_session_port.create_client_secret(
            instructions=exam.build_realtime_instructions()
        )
        now = datetime.now(UTC)
        session = exam.start_session(
            student_id=current_user.id,
            started_at=now,
            attempt_number=1,
            expires_at=secret.expires_at,
            provider_session_id=secret.provider_session_id,
        )
        await self.session_repository.save(session)
        await self.result_repository.save(session.create_pending_result())
        return StartedExamSession(
            session=session,
            client_secret=secret.value,
        )

    async def list_my_exam_results(
        self,
        *,
        exam_id: UUID,
        current_user: CurrentUser,
    ) -> Sequence[ExamResult]:
        if current_user.role != UserRole.STUDENT:
            raise AuthForbiddenException()
        exam = await self.repository.get_by_id(exam_id)
        if exam is None:
            raise ExamNotFoundException()
        await self.classroom_usecase.get_classroom(
            classroom_id=exam.classroom_id,
            current_user=current_user,
        )
        return await self.result_repository.list_by_exam_and_student(
            exam_id=exam_id,
            student_id=current_user.id,
        )

    @transactional
    async def record_exam_turn(
        self,
        *,
        exam_id: UUID,
        session_id: UUID,
        current_user: CurrentUser,
        command: RecordExamTurnCommand,
    ) -> ExamTurn:
        if current_user.role != UserRole.STUDENT:
            raise AuthForbiddenException()
        exam = await self.repository.get_by_id(exam_id)
        if exam is None:
            raise ExamNotFoundException()
        await self.classroom_usecase.get_classroom(
            classroom_id=exam.classroom_id,
            current_user=current_user,
        )
        session = await self.session_repository.get_by_id(session_id)
        if session is None:
            raise AuthForbiddenException()
        existing_turns = await self.turn_repository.list_by_session(
            session_id=session_id,
        )
        turn = exam.record_turn(
            session=session,
            student_id=current_user.id,
            role=command.role,
            event_type=command.event_type,
            content=command.content,
            created_at=command.occurred_at,
            metadata=command.metadata,
            existing_turns=existing_turns,
        )
        await self.turn_repository.save(turn)
        await self.session_repository.save(session)
        return turn

    @transactional
    async def complete_exam_session(
        self,
        *,
        exam_id: UUID,
        session_id: UUID,
        current_user: CurrentUser,
        command: CompleteExamSessionCommand,
    ) -> ExamSession:
        if current_user.role != UserRole.STUDENT:
            raise AuthForbiddenException()
        exam = await self.repository.get_by_id(exam_id)
        if exam is None:
            raise ExamNotFoundException()
        await self.classroom_usecase.get_classroom(
            classroom_id=exam.classroom_id,
            current_user=current_user,
        )
        session = await self.session_repository.get_by_id(session_id)
        if session is None:
            raise AuthForbiddenException()
        exam.complete_session(
            session=session,
            student_id=current_user.id,
            occurred_at=command.occurred_at,
        )
        await self.session_repository.save(session)
        return session

    @transactional
    async def finalize_exam_result(
        self,
        *,
        exam_id: UUID,
        session_id: UUID,
        current_user: CurrentUser,
        command: FinalizeExamResultCommand,
    ) -> ExamResult:
        if current_user.role != UserRole.STUDENT:
            raise AuthForbiddenException()
        exam = await self.repository.get_by_id(exam_id)
        if exam is None:
            raise ExamNotFoundException()
        await self.classroom_usecase.get_classroom(
            classroom_id=exam.classroom_id,
            current_user=current_user,
        )
        session = await self.session_repository.get_by_id(session_id)
        if session is None:
            raise AuthForbiddenException()
        results = await self.result_repository.list_by_exam_and_student(
            exam_id=exam_id,
            student_id=current_user.id,
        )
        result = exam.finalize_result(
            session=session,
            student_id=current_user.id,
            results=results,
            overall_score=command.overall_score,
            summary=command.summary,
            submitted_at=command.occurred_at,
        )
        await self.result_repository.save(result)
        return result

