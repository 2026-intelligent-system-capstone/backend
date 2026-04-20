from collections.abc import Sequence
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy.exc import IntegrityError

from app.async_job.application.service import AsyncJobService
from app.async_job.domain.entity import AsyncJobTargetType, AsyncJobType
from app.auth.application.exception import AuthForbiddenException
from app.auth.domain.entity import CurrentUser
from app.classroom.domain.entity import ClassroomMaterialIngestStatus
from app.classroom.domain.usecase import ClassroomUseCase
from app.exam.application.exception import (
    ExamNotFoundException,
    ExamQuestionGenerationAlreadyInProgressException,
    ExamQuestionGenerationContextUnavailableException,
    ExamQuestionGenerationFailedException,
    ExamQuestionGenerationMaterialIngestFailedException,
    ExamQuestionGenerationMaterialNotFoundException,
    ExamQuestionGenerationMaterialNotReadyException,
    ExamQuestionGenerationUnavailableException,
    ExamQuestionInvalidPayloadException,
    ExamQuestionNotFoundException,
    ExamSessionAlreadyInProgressException,
    ExamSessionMaxAttemptsExceededException,
    ExamSessionUnavailableException,
)
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
    ExamGenerationStatus,
    ExamQuestion,
    ExamQuestionStatus,
    ExamQuestionType,
    ExamQuestionTypeStrategy,
    ExamResult,
    ExamResultStatus,
    ExamSession,
    ExamStatus,
    ExamTurn,
    StartedExamSession,
    StudentExam,
)
from app.exam.domain.exception import (
    ExamQuestionNotFoundDomainException,
    ExamSessionAlreadyInProgressDomainException,
    ExamSessionMaxAttemptsExceededDomainException,
)
from app.exam.domain.repository import (
    ExamRepository,
    ExamResultRepository,
    ExamSessionRepository,
    ExamTurnRepository,
)
from app.exam.domain.service import (
    ExamQuestionGenerationCriterion,
    ExamQuestionGenerationLevelCount,
    ExamQuestionGenerationPort,
    ExamQuestionGenerationSubmitResult,
    ExamQuestionGenerationTypeCount,
    ExamQuestionSourceMaterial,
    GenerateExamQuestionsRequest,
    RealtimeSessionPort,
)
from app.exam.domain.usecase import ExamUseCase
from app.user.domain.entity import UserRole
from core.db.session import session
from core.db.transactional import transactional


UNIQUE_ATTEMPT_CONSTRAINT_NAME = "uq_t_exam_session_exam_student_attempt"
SINGLE_IN_PROGRESS_INDEX_NAME = "ix_t_exam_session_single_in_progress"


class ExamService(ExamUseCase):
    def _normalize_question_type_counts(
        self,
        *,
        total_question_count: int,
        strategy: ExamQuestionTypeStrategy,
    ) -> list[ExamQuestionGenerationTypeCount]:
        ordered_types = strategy.ordered_question_types()
        counts = {question_type: 0 for question_type in ordered_types}

        seeded_types = ordered_types[:total_question_count]
        for question_type in seeded_types:
            counts[question_type] += 1

        remaining = total_question_count - len(seeded_types)
        cycle = strategy.weighted_cycle()
        index = 0
        while remaining > 0:
            question_type = cycle[index % len(cycle)]
            counts[question_type] += 1
            remaining -= 1
            index += 1

        return [
            ExamQuestionGenerationTypeCount(
                question_type=question_type,
                count=counts[question_type],
            )
            for question_type in ordered_types
            if counts[question_type] > 0
        ]

    def _map_exam_session_integrity_error(self, error: IntegrityError) -> None:
        awaitable_message = str(error.orig) if error.orig is not None else str(error)
        if SINGLE_IN_PROGRESS_INDEX_NAME in awaitable_message:
            raise ExamSessionAlreadyInProgressException() from error
        if UNIQUE_ATTEMPT_CONSTRAINT_NAME in awaitable_message:
            raise ExamSessionMaxAttemptsExceededException() from error
        raise error

    def __init__(
        self,
        *,
        repository: ExamRepository,
        classroom_usecase: ClassroomUseCase,
        session_repository: ExamSessionRepository,
        result_repository: ExamResultRepository,
        turn_repository: ExamTurnRepository,
        realtime_session_port: RealtimeSessionPort,
        question_generation_port: ExamQuestionGenerationPort | None = None,
        async_job_service: AsyncJobService | None = None,
    ):
        self.repository = repository
        self.classroom_usecase = classroom_usecase
        self.session_repository = session_repository
        self.result_repository = result_repository
        self.turn_repository = turn_repository
        self.realtime_session_port = realtime_session_port
        self.question_generation_port = question_generation_port
        self.async_job_service = async_job_service

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
            max_attempts=command.max_attempts,
            week=command.week,
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

    def _is_exam_session_available(
        self,
        *,
        exam: Exam,
        now: datetime,
    ) -> bool:
        return (
            exam.status is not ExamStatus.CLOSED
            and exam.starts_at <= now <= exam.ends_at
        )

    def _has_completed_exam_result(
        self,
        *,
        results: Sequence[ExamResult],
    ) -> bool:
        return any(
            result.status is ExamResultStatus.COMPLETED for result in results
        )

    def _select_latest_result(
        self,
        *,
        results: Sequence[ExamResult],
    ) -> ExamResult | None:
        completed_results = [
            result
            for result in results
            if result.status is ExamResultStatus.COMPLETED
        ]
        if completed_results:
            return max(
                completed_results,
                key=lambda result: (
                    result.submitted_at or datetime.min.replace(tzinfo=UTC),
                    str(result.id),
                ),
            )
        if not results:
            return None
        return max(
            results,
            key=lambda result: (
                result.submitted_at or datetime.min.replace(tzinfo=UTC),
                str(result.id),
            ),
        )

    async def _build_student_exam(
        self,
        *,
        exam: Exam,
        student_id: UUID,
    ) -> StudentExam:
        results = await self.result_repository.list_by_exam_and_student(
            exam_id=exam.id,
            student_id=student_id,
        )
        latest_result = self._select_latest_result(results=results)
        has_completed_result = self._has_completed_exam_result(results=results)
        is_completed = exam.status is ExamStatus.CLOSED or has_completed_result
        can_enter = not is_completed and self._is_exam_session_available(
            exam=exam,
            now=datetime.now(UTC),
        )
        return StudentExam(
            exam=exam,
            is_completed=is_completed,
            can_enter=can_enter,
            latest_result=latest_result,
        )

    async def list_student_exams(
        self,
        *,
        current_user: CurrentUser,
    ) -> Sequence[StudentExam]:
        if current_user.role != UserRole.STUDENT:
            raise AuthForbiddenException()
        classrooms = await self.classroom_usecase.list_classrooms(
            current_user=current_user,
        )
        accessible_classroom_ids = {classroom.id for classroom in classrooms}
        exams = await self.repository.list()
        student_exams: list[StudentExam] = []
        for exam in exams:
            if exam.classroom_id not in accessible_classroom_ids:
                continue
            student_exams.append(
                await self._build_student_exam(
                    exam=exam,
                    student_id=current_user.id,
                )
            )
        return student_exams

    async def get_student_exam(
        self,
        *,
        exam_id: UUID,
        current_user: CurrentUser,
    ) -> StudentExam:
        if current_user.role != UserRole.STUDENT:
            raise AuthForbiddenException()
        exam = await self.repository.get_by_id(exam_id)
        if exam is None:
            raise ExamNotFoundException()
        classrooms = await self.classroom_usecase.list_classrooms(
            current_user=current_user,
        )
        accessible_classroom_ids = {classroom.id for classroom in classrooms}
        if exam.classroom_id not in accessible_classroom_ids:
            raise ExamNotFoundException()
        return await self._build_student_exam(
            exam=exam,
            student_id=current_user.id,
        )

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
    async def create_exam_question(
        self,
        *,
        classroom_id: UUID,
        exam_id: UUID,
        current_user: CurrentUser,
        command: CreateExamQuestionCommand,
    ) -> ExamQuestion:
        exam = await self.get_exam(
            classroom_id=classroom_id,
            exam_id=exam_id,
            current_user=current_user,
        )
        if current_user.role not in {UserRole.PROFESSOR, UserRole.ADMIN}:
            raise AuthForbiddenException()
        try:
            question = exam.add_question(
                question_number=command.question_number,
                max_score=command.max_score,
                question_type=command.question_type,
                bloom_level=command.bloom_level,
                difficulty=command.difficulty,
                question_text=command.question_text,
                intent_text=command.intent_text,
                rubric_text=command.rubric_text,
                answer_options=command.answer_options,
                correct_answer_text=command.correct_answer_text,
                source_material_ids=command.source_material_ids,
            )
        except ValueError as exc:
            raise ExamQuestionInvalidPayloadException() from exc
        await self.repository.save(exam)
        return question

    @transactional
    async def update_exam_question(
        self,
        *,
        classroom_id: UUID,
        exam_id: UUID,
        question_id: UUID,
        current_user: CurrentUser,
        command: UpdateExamQuestionCommand,
    ) -> ExamQuestion:
        exam = await self.get_exam(
            classroom_id=classroom_id,
            exam_id=exam_id,
            current_user=current_user,
        )
        if current_user.role not in {UserRole.PROFESSOR, UserRole.ADMIN}:
            raise AuthForbiddenException()
        try:
            current_question = exam.find_question(question_id)
            effective_question_type = (
                command.question_type or current_question.question_type
            )
            effective_answer_options = (
                command.answer_options
                if "answer_options" in command.model_fields_set
                else current_question.answer_options
            )
            effective_correct_answer_text = (
                command.correct_answer_text
                if "correct_answer_text" in command.model_fields_set
                else current_question.correct_answer_text
            )
            effective_rubric_text = (
                command.rubric_text
                if "rubric_text" in command.model_fields_set
                else current_question.rubric_text
            )
            should_validate_oral = (
                effective_question_type is ExamQuestionType.ORAL
                and (
                    command.question_type is ExamQuestionType.ORAL
                    or "rubric_text" in command.model_fields_set
                )
            )
            if should_validate_oral and not (effective_rubric_text or "").strip():
                raise ExamQuestionInvalidPayloadException()
            should_validate_subjective = (
                effective_question_type is ExamQuestionType.SUBJECTIVE
                and (
                    command.question_type is ExamQuestionType.SUBJECTIVE
                    or "correct_answer_text" in command.model_fields_set
                )
            )
            if should_validate_subjective and not (
                effective_correct_answer_text or ""
            ).strip():
                raise ExamQuestionInvalidPayloadException()
            should_validate_multiple_choice = (
                effective_question_type is ExamQuestionType.MULTIPLE_CHOICE
                and (
                    command.question_type is ExamQuestionType.MULTIPLE_CHOICE
                    or "answer_options" in command.model_fields_set
                    or "correct_answer_text" in command.model_fields_set
                )
            )
            if should_validate_multiple_choice:
                if not effective_answer_options:
                    raise ExamQuestionInvalidPayloadException()
                if effective_correct_answer_text is None:
                    raise ExamQuestionInvalidPayloadException()
                if effective_correct_answer_text not in effective_answer_options:
                    raise ExamQuestionInvalidPayloadException()
            question = exam.update_question(
                question_id=question_id,
                question_number=command.question_number,
                max_score=command.max_score,
                question_type=command.question_type,
                bloom_level=command.bloom_level,
                difficulty=command.difficulty,
                question_text=command.question_text,
                intent_text=command.intent_text,
                rubric_text=command.rubric_text,
                answer_options=command.answer_options,
                correct_answer_text=command.correct_answer_text,
                source_material_ids=command.source_material_ids,
            )
        except ExamQuestionNotFoundDomainException as exc:
            raise ExamQuestionNotFoundException() from exc
        except ValueError as exc:
            raise ExamQuestionInvalidPayloadException() from exc
        await self.repository.save(exam)
        return question

    @transactional
    async def delete_exam_question(
        self,
        *,
        classroom_id: UUID,
        exam_id: UUID,
        question_id: UUID,
        current_user: CurrentUser,
    ) -> ExamQuestion:
        exam = await self.get_exam(
            classroom_id=classroom_id,
            exam_id=exam_id,
            current_user=current_user,
        )
        if current_user.role not in {UserRole.PROFESSOR, UserRole.ADMIN}:
            raise AuthForbiddenException()
        try:
            question = exam.delete_question(question_id)
        except ExamQuestionNotFoundDomainException as exc:
            raise ExamQuestionNotFoundException() from exc
        await self.repository.save(exam)
        return question

    @transactional
    async def generate_exam_questions(
        self,
        *,
        classroom_id: UUID,
        exam_id: UUID,
        current_user: CurrentUser,
        command: GenerateExamQuestionsCommand,
    ) -> ExamQuestionGenerationSubmitResult:
        exam = await self.get_exam(
            classroom_id=classroom_id,
            exam_id=exam_id,
            current_user=current_user,
        )
        if current_user.role not in {UserRole.PROFESSOR, UserRole.ADMIN}:
            raise AuthForbiddenException()
        if self.question_generation_port is None or self.async_job_service is None:
            raise ExamQuestionGenerationUnavailableException()
        if exam.generation_status in {
            ExamGenerationStatus.QUEUED,
            ExamGenerationStatus.RUNNING,
        }:
            raise ExamQuestionGenerationAlreadyInProgressException()

        classroom = await self.classroom_usecase.get_classroom(
            classroom_id=classroom_id,
            current_user=current_user,
        )
        source_materials = []
        if command.source_material_ids:
            materials = await self.classroom_usecase.list_classroom_materials(
                classroom_id=classroom.id,
                current_user=current_user,
            )
            selected_material_ids = set(command.source_material_ids)
            material_map = {
                result.material.id: result
                for result in materials
                if result.material.id in selected_material_ids
            }
            missing_material_ids = selected_material_ids - set(material_map)
            if missing_material_ids:
                raise ExamQuestionGenerationMaterialNotFoundException()
            selected_materials = [
                material_map[material_id]
                for material_id in command.source_material_ids
            ]
            if any(
                material.material.ingest_status
                is ClassroomMaterialIngestStatus.FAILED
                for material in selected_materials
            ):
                raise ExamQuestionGenerationMaterialIngestFailedException()
            if any(
                material.material.ingest_status
                is not ClassroomMaterialIngestStatus.COMPLETED
                for material in selected_materials
            ):
                raise ExamQuestionGenerationMaterialNotReadyException()
            source_materials = [
                ExamQuestionSourceMaterial(
                    material_id=material_id,
                    file_name=material_map[material_id].file.file_name,
                    title=material_map[material_id].material.title,
                    week=material_map[material_id].material.week,
                )
                for material_id in command.source_material_ids
            ]

        question_type_counts = (
            [
                ExamQuestionGenerationTypeCount(
                    question_type=item.question_type,
                    count=item.count,
                )
                for item in command.question_type_counts
            ]
            if command.question_type_counts is not None
            else self._normalize_question_type_counts(
                total_question_count=command.total_question_count or 0,
                strategy=command.question_type_strategy
                or ExamQuestionTypeStrategy.BALANCED,
            )
        )

        generation_request = GenerateExamQuestionsRequest(
            exam_id=exam.id,
            classroom_id=classroom.id,
            title=exam.title,
            exam_type=exam.exam_type,
            scope_text=command.scope_text,
            max_follow_ups=command.max_follow_ups,
            difficulty=command.difficulty,
            criteria=[
                ExamQuestionGenerationCriterion(
                    title=criterion.title,
                    description=criterion.description,
                    weight=criterion.weight,
                    excellent_definition=criterion.excellent_definition,
                    average_definition=criterion.average_definition,
                    poor_definition=criterion.poor_definition,
                )
                for criterion in exam.criteria
            ],
            bloom_counts=[
                ExamQuestionGenerationLevelCount(
                    bloom_level=item.bloom_level,
                    count=item.count,
                )
                for item in command.bloom_counts
            ],
            question_type_counts=question_type_counts,
            source_materials=source_materials,
        )
        job = await self.async_job_service.enqueue(
            job_type=AsyncJobType.EXAM_QUESTION_GENERATION,
            target_type=AsyncJobTargetType.EXAM,
            target_id=exam.id,
            requested_by=current_user.id,
            payload={
                "exam_id": str(exam.id),
                "classroom_id": str(classroom.id),
                "request": {
                    "scope_text": generation_request.scope_text,
                    "max_follow_ups": generation_request.max_follow_ups,
                    "difficulty": generation_request.difficulty.value,
                    "source_material_ids": [
                        str(material_id)
                        for material_id in command.source_material_ids
                    ],
                    "bloom_counts": [
                        {
                            "bloom_level": item.bloom_level.value,
                            "count": item.count,
                        }
                        for item in command.bloom_counts
                    ],
                    "question_type_counts": [
                        {
                            "question_type": item.question_type.value,
                            "count": item.count,
                        }
                        for item in question_type_counts
                    ],
                },
            },
            dedupe_key=f"exam-question-generation:{exam.id}",
        )
        exam.mark_generation_queued(
            job_id=job.id,
            requested_at=datetime.now(UTC),
        )
        await self.repository.save(exam)
        return ExamQuestionGenerationSubmitResult(
            exam_id=exam.id,
            generation_status=exam.generation_status,
            job=job.to_reference(),
            generation_requested_at=exam.generation_requested_at,
            generation_error=exam.generation_error,
        )

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
        if not self._is_exam_session_available(
            exam=exam,
            now=datetime.now(UTC),
        ):
            raise ExamSessionUnavailableException()
        existing_results = await self.result_repository.list_by_exam_and_student(
            exam_id=exam.id,
            student_id=current_user.id,
        )
        if self._has_completed_exam_result(results=existing_results):
            raise ExamSessionUnavailableException()
        existing_sessions = (
            await self.session_repository.list_by_exam_and_student_for_update(
                exam_id=exam.id,
                student_id=current_user.id,
            )
        )
        try:
            attempt_number = exam.resolve_next_attempt_number(
                sessions=existing_sessions,
            )
        except ExamSessionAlreadyInProgressDomainException as exc:
            raise ExamSessionAlreadyInProgressException() from exc
        except ExamSessionMaxAttemptsExceededDomainException as exc:
            raise ExamSessionMaxAttemptsExceededException() from exc
        now = datetime.now(UTC)
        session_entity = exam.start_session(
            student_id=current_user.id,
            started_at=now,
            attempt_number=attempt_number,
        )
        try:
            await self.session_repository.save(session_entity)
            await self.result_repository.save(
                session_entity.create_pending_result()
            )
            await session.flush()
        except IntegrityError as exc:
            self._map_exam_session_integrity_error(exc)
        secret = await self.realtime_session_port.create_client_secret(
            instructions=exam.build_realtime_instructions()
        )
        session_entity.expires_at = secret.expires_at
        session_entity.provider_session_id = secret.provider_session_id
        await self.session_repository.save(session_entity)
        await session.flush()
        return StartedExamSession(
            session=session_entity,
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
        if self.async_job_service is not None:
            await self.async_job_service.enqueue(
                job_type=AsyncJobType.EXAM_RESULT_EVALUATION,
                target_type=AsyncJobTargetType.EXAM,
                target_id=exam.id,
                requested_by=current_user.id,
                payload={
                    "exam_id": str(exam.id),
                    "session_id": str(session.id),
                    "student_id": str(current_user.id),
                },
                dedupe_key=f"exam-result-evaluation:{session.id}",
            )
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
        )
        return result
