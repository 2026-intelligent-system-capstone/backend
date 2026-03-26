from collections.abc import Sequence
from datetime import UTC, datetime
from uuid import UUID

from app.auth.application.exception import AuthForbiddenException
from app.auth.domain.entity import CurrentUser
from app.classroom.domain.usecase import ClassroomUseCase
from app.exam.application.exception import ExamNotFoundException
from app.exam.domain.command import CreateExamCommand
from app.exam.domain.entity import (
    Exam,
    ExamCriterion,
    ExamResult,
    ExamResultStatus,
    ExamSession,
    ExamSessionStatus,
    ExamStatus,
    StartedExamSession,
)
from app.exam.domain.repository import (
    ExamRepository,
    ExamResultRepository,
    ExamSessionRepository,
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
        session_repository: ExamSessionRepository | None = None,
        result_repository: ExamResultRepository | None = None,
        realtime_session_port: RealtimeSessionPort | None = None,
    ):
        self.repository = repository
        self.classroom_usecase = classroom_usecase
        self.session_repository = session_repository
        self.result_repository = result_repository
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
        exam = Exam(
            classroom_id=classroom_id,
            title=command.title,
            description=command.description,
            exam_type=command.exam_type,
            status=ExamStatus.READY,
            duration_minutes=command.duration_minutes,
            starts_at=command.starts_at,
            ends_at=command.ends_at,
            allow_retake=command.allow_retake,
        )
        exam.criteria = [
            ExamCriterion(
                exam_id=exam.id,
                title=criterion.title,
                description=criterion.description,
                weight=criterion.weight,
                sort_order=criterion.sort_order,
                excellent_definition=criterion.excellent_definition,
                average_definition=criterion.average_definition,
                poor_definition=criterion.poor_definition,
            )
            for criterion in command.criteria
        ]
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
        if exam is None or exam.classroom_id != classroom_id:
            raise ExamNotFoundException()
        return exam

    @transactional
    async def start_exam_session(
        self,
        *,
        classroom_id: UUID,
        exam_id: UUID,
        current_user: CurrentUser,
    ) -> StartedExamSession:
        self._ensure_student(current_user)
        exam = await self.get_exam(
            classroom_id=classroom_id,
            exam_id=exam_id,
            current_user=current_user,
        )
        session_repository = self._get_session_repository()
        realtime_session_port = self._get_realtime_session_port()
        secret = await realtime_session_port.create_client_secret(
            instructions=self._build_realtime_instructions(exam)
        )
        now = datetime.now(UTC)
        session = ExamSession(
            exam_id=exam.id,
            student_id=current_user.id,
            status=ExamSessionStatus.IN_PROGRESS,
            started_at=now,
            last_activity_at=now,
            attempt_number=1,
            expires_at=secret.expires_at,
            provider_session_id=secret.provider_session_id,
        )
        await session_repository.save(session)
        await self._get_result_repository().save(
            ExamResult(
                exam_id=exam.id,
                session_id=session.id,
                student_id=current_user.id,
                status=ExamResultStatus.PENDING,
            )
        )
        return StartedExamSession(
            session=session,
            client_secret=secret.value,
        )

    async def list_my_exam_results(
        self,
        *,
        classroom_id: UUID,
        exam_id: UUID,
        current_user: CurrentUser,
    ) -> Sequence[ExamResult]:
        self._ensure_student(current_user)
        await self.get_exam(
            classroom_id=classroom_id,
            exam_id=exam_id,
            current_user=current_user,
        )
        return await self._get_result_repository().list_by_exam_and_student(
            exam_id=exam_id,
            student_id=current_user.id,
        )

    def _get_session_repository(self) -> ExamSessionRepository:
        if self.session_repository is None:
            raise RuntimeError("Exam session repository is not configured")
        return self.session_repository

    def _get_realtime_session_port(self) -> RealtimeSessionPort:
        if self.realtime_session_port is None:
            raise RuntimeError("Realtime session port is not configured")
        return self.realtime_session_port

    def _get_result_repository(self) -> ExamResultRepository:
        if self.result_repository is None:
            raise RuntimeError("Exam result repository is not configured")
        return self.result_repository

    @staticmethod
    def _ensure_student(current_user: CurrentUser) -> None:
        if current_user.role != UserRole.STUDENT:
            raise AuthForbiddenException()

    @staticmethod
    def _build_realtime_instructions(exam: Exam) -> str:
        criteria_lines = "\n".join(
            (
                (
                    f"- {criterion.sort_order}. {criterion.title} "
                    f"({criterion.weight}%)"
                )
                + (
                    f": {criterion.description}"
                    if criterion.description
                    else ""
                )
            )
            for criterion in exam.criteria
        )
        return (
            f"시험 제목: {exam.title}\n"
            f"시험 설명: {exam.description or '설명 없음'}\n"
            f"시험 유형: {exam.exam_type.value}\n"
            f"제한 시간(분): {exam.duration_minutes}\n"
            "평가 기준:\n"
            f"{criteria_lines}"
        )
