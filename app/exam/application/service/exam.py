from collections.abc import Sequence
from datetime import UTC, datetime
from uuid import UUID

from app.auth.application.exception import AuthForbiddenException
from app.auth.domain.entity import CurrentUser
from app.classroom.domain.entity import ClassroomMaterialIngestStatus
from app.classroom.domain.usecase import ClassroomUseCase
from app.exam.application.exception import (
    ExamNotFoundException,
    ExamQuestionGenerationContextUnavailableException,
    ExamQuestionGenerationFailedException,
    ExamQuestionGenerationMaterialIngestFailedException,
    ExamQuestionGenerationMaterialNotFoundException,
    ExamQuestionGenerationMaterialNotReadyException,
    ExamQuestionGenerationUnavailableException,
    ExamQuestionNotFoundException,
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
    ExamQuestion,
    ExamQuestionStatus,
    ExamResult,
    ExamSession,
    ExamTurn,
    StartedExamSession,
)
from app.exam.domain.exception import ExamQuestionNotFoundDomainException
from app.exam.domain.repository import (
    ExamRepository,
    ExamResultRepository,
    ExamSessionRepository,
    ExamTurnRepository,
)
from app.exam.domain.service import (
    ExamQuestionGenerationCriterion,
    ExamQuestionGenerationPort,
    ExamQuestionGenerationRatio,
    ExamQuestionSourceMaterial,
    GenerateExamQuestionsRequest,
    RealtimeSessionPort,
)
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
        question_generation_port: ExamQuestionGenerationPort | None = None,
    ):
        self.repository = repository
        self.classroom_usecase = classroom_usecase
        self.session_repository = session_repository
        self.result_repository = result_repository
        self.turn_repository = turn_repository
        self.realtime_session_port = realtime_session_port
        self.question_generation_port = question_generation_port

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
        question = exam.add_question(
            question_number=command.question_number,
            bloom_level=command.bloom_level,
            difficulty=command.difficulty,
            question_text=command.question_text,
            scope_text=command.scope_text,
            evaluation_objective=command.evaluation_objective,
            answer_key=command.answer_key,
            scoring_criteria=command.scoring_criteria,
            source_material_ids=command.source_material_ids,
        )
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
            question = exam.update_question(
                question_id=question_id,
                question_number=command.question_number,
                bloom_level=command.bloom_level,
                difficulty=command.difficulty,
                question_text=command.question_text,
                scope_text=command.scope_text,
                evaluation_objective=command.evaluation_objective,
                answer_key=command.answer_key,
                scoring_criteria=command.scoring_criteria,
                source_material_ids=command.source_material_ids,
            )
        except ExamQuestionNotFoundDomainException as exc:
            raise ExamQuestionNotFoundException() from exc
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
    ) -> Sequence[ExamQuestion]:
        exam = await self.get_exam(
            classroom_id=classroom_id,
            exam_id=exam_id,
            current_user=current_user,
        )
        if current_user.role not in {UserRole.PROFESSOR, UserRole.ADMIN}:
            raise AuthForbiddenException()
        if self.question_generation_port is None:
            raise ExamQuestionGenerationUnavailableException()

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

        try:
            drafts = await self.question_generation_port.generate_questions(
                request=GenerateExamQuestionsRequest(
                    exam_id=exam.id,
                    classroom_id=classroom.id,
                    title=exam.title,
                    exam_type=exam.exam_type,
                    scope_text=command.scope_text,
                    total_questions=command.total_questions,
                    max_follow_ups=command.max_follow_ups,
                    difficulty=command.difficulty,
                    criteria=[
                        ExamQuestionGenerationCriterion(
                            title=criterion.title,
                            description=criterion.description,
                            weight=criterion.weight,
                            excellent_definition=(
                                criterion.excellent_definition
                            ),
                            average_definition=criterion.average_definition,
                            poor_definition=criterion.poor_definition,
                        )
                        for criterion in exam.criteria
                    ],
                    bloom_ratios=[
                        ExamQuestionGenerationRatio(
                            bloom_level=item.bloom_level,
                            percentage=item.percentage,
                        )
                        for item in command.bloom_ratios
                    ],
                    source_materials=source_materials,
                )
            )
        except (
            ExamQuestionGenerationContextUnavailableException,
            ExamQuestionGenerationFailedException,
            ExamQuestionGenerationUnavailableException,
        ):
            raise
        next_question_number = (
            max(
                (
                    question.question_number
                    for question in exam.questions
                    if question.status is not ExamQuestionStatus.DELETED
                ),
                default=0,
            )
            + 1
        )
        questions = []
        for offset, draft in enumerate(drafts):
            questions.append(
                exam.add_question(
                    question_number=next_question_number + offset,
                    bloom_level=draft.bloom_level,
                    difficulty=draft.difficulty,
                    question_text=draft.question_text,
                    scope_text=draft.scope_text,
                    evaluation_objective=draft.evaluation_objective,
                    answer_key=draft.answer_key,
                    scoring_criteria=draft.scoring_criteria,
                    source_material_ids=draft.source_material_ids,
                )
            )
        await self.repository.save(exam)
        return questions

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
