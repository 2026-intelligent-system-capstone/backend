import asyncio
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID

from app.async_job.domain.entity import AsyncJob, AsyncJobType
from app.async_job.domain.repository import AsyncJobRepository
from app.classroom.domain.entity import (
    ClassroomMaterial,
    ClassroomMaterialIngestStatus,
    ClassroomMaterialScopeCandidate,
    ClassroomMaterialSourceKind,
)
from app.classroom.domain.exception import (
    ClassroomMaterialIngestDomainException,
    ClassroomMaterialIngestEmptyScopeDomainException,
)
from app.classroom.domain.repository.classroom import ClassroomRepository
from app.classroom.domain.repository.classroom_material import (
    ClassroomMaterialRepository,
)
from app.classroom.domain.service import ClassroomMaterialIngestPort
from app.classroom.domain.service.material_ingest import (
    ClassroomMaterialIngestRequest,
    validate_classroom_material_source_url,
)
from app.exam.application.exception import (
    ExamQuestionGenerationFailedException,
    ExamQuestionGenerationMaterialIngestFailedException,
    ExamQuestionGenerationMaterialNotFoundException,
    ExamQuestionGenerationMaterialNotReadyException,
    ExamQuestionGenerationUnavailableException,
)
from app.exam.domain.entity import (
    BloomLevel,
    Exam,
    ExamDifficulty,
    ExamQuestionType,
    ExamResult,
    ExamResultCriterion,
    ExamResultStatus,
    ExamTurnEventType,
    ExamTurnRole,
)
from app.exam.domain.repository.exam import (
    ExamRepository,
    ExamResultRepository,
    ExamSessionRepository,
    ExamTurnRepository,
)
from app.exam.domain.service import (
    EvaluateExamResult,
    EvaluateExamResultRequest,
    ExamQuestionGenerationCriterion,
    ExamQuestionGenerationLevelCount,
    ExamQuestionGenerationPort,
    ExamQuestionGenerationTypeCount,
    ExamQuestionSourceMaterial,
    ExamResultEvaluationCriterion,
    ExamResultEvaluationCriterionScore,
    ExamResultEvaluationPort,
    ExamResultEvaluationQuestion,
    ExamResultEvaluationTurn,
    GeneratedExamQuestionDraft,
    GenerateExamQuestionsRequest,
)
from app.file.domain.entity.file import File
from app.file.domain.usecase.file import FileUseCase
from core.common.exceptions.base import CustomException
from core.db.transactional import transactional


@dataclass(frozen=True)
class MaterialIngestExecution:
    material: ClassroomMaterial
    classroom_id: UUID
    file: File | None


@dataclass(frozen=True)
class ExamGenerationExecution:
    exam: Exam


@dataclass(frozen=True)
class ExamResultEvaluationExecution:
    exam: Exam
    session_id: UUID
    student_id: UUID
    result: ExamResult


class AsyncJobWorker:
    def __init__(
        self,
        *,
        repository: AsyncJobRepository,
        classroom_repository: ClassroomRepository,
        material_repository: ClassroomMaterialRepository,
        file_usecase: FileUseCase,
        material_ingest_port: ClassroomMaterialIngestPort | None = None,
        exam_repository: ExamRepository,
        question_generation_port: ExamQuestionGenerationPort | None = None,
        exam_session_repository: ExamSessionRepository | None = None,
        exam_result_repository: ExamResultRepository | None = None,
        exam_turn_repository: ExamTurnRepository | None = None,
        result_evaluation_port: ExamResultEvaluationPort | None = None,
    ):
        self.repository = repository
        self.classroom_repository = classroom_repository
        self.material_repository = material_repository
        self.file_usecase = file_usecase
        self.material_ingest_port = material_ingest_port
        self.exam_repository = exam_repository
        self.question_generation_port = question_generation_port
        self.exam_session_repository = exam_session_repository
        self.exam_result_repository = exam_result_repository
        self.exam_turn_repository = exam_turn_repository
        self.result_evaluation_port = result_evaluation_port

    async def run_next_queued_job(self) -> bool:
        job = await self._claim_next_job()
        if job is None:
            return False

        try:
            if job.job_type is AsyncJobType.MATERIAL_INGEST:
                execution = await self._prepare_material_ingest_job(job.id)
                if execution is None:
                    return True
                await self._execute_material_ingest_job(
                    job_id=job.id,
                    material=execution.material,
                    classroom_id=execution.classroom_id,
                    file=execution.file,
                )
                return True

            if job.job_type is AsyncJobType.EXAM_QUESTION_GENERATION:
                execution = await self._prepare_exam_generation_job(job.id)
                if execution is None:
                    return True
                await self._execute_exam_generation_job(
                    job_id=job.id,
                    exam=execution.exam,
                )
                return True

            if job.job_type is AsyncJobType.EXAM_RESULT_EVALUATION:
                execution = await self._prepare_exam_result_evaluation_job(
                    job.id
                )
                if execution is None:
                    return True
                await self._execute_exam_result_evaluation_job(
                    job_id=job.id,
                    exam=execution.exam,
                    session_id=execution.session_id,
                    student_id=execution.student_id,
                    result=execution.result,
                )
                return True

            await self._fail_job(
                job_id=job.id,
                error_message="지원하지 않는 비동기 작업입니다.",
            )
            return True
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            await self._fail_job(
                job_id=job.id,
                error_message=self._resolve_error_message(exc),
            )
            return True

    @transactional
    async def _claim_next_job(self) -> AsyncJob | None:
        job = await self.repository.claim_next_runnable(now=datetime.now(UTC))
        if job is None:
            return None

        job.mark_running(started_at=datetime.now(UTC))
        await self.repository.save(job)
        return job

    @transactional
    async def _prepare_material_ingest_job(
        self,
        job_id: UUID,
    ) -> MaterialIngestExecution | None:
        job = await self.repository.get_by_id(job_id)
        if job is None:
            return None

        material = await self.material_repository.get_by_id(job.target_id)
        if material is None:
            job.mark_failed(error_message="강의 자료를 찾을 수 없습니다.")
            await self.repository.save(job)
            return None

        classroom = await self.classroom_repository.get_by_id(
            material.classroom_id
        )
        if classroom is None:
            job.mark_failed(error_message="강의실을 찾을 수 없습니다.")
            await self.repository.save(job)
            return None

        if self.material_ingest_port is None or not material.supports_ingest():
            job.mark_completed(
                result={
                    "material_id": str(material.id),
                    "ingest_status": material.ingest_status.value,
                    "skipped": True,
                }
            )
            await self.repository.save(job)
            return None

        try:
            file = await self._load_material_file(material.file_id)
        except Exception:
            material.mark_ingest_failed(
                "강의 자료 적재 중 오류가 발생했습니다."
            )
            await self.material_repository.save(material)
            job.mark_failed(
                error_message=material.ingest_error
                or "강의 자료 적재 중 오류가 발생했습니다."
            )
            await self.repository.save(job)
            return None

        material.mark_ingest_pending()
        await self.material_repository.save(material)
        return MaterialIngestExecution(
            material=material,
            classroom_id=classroom.id,
            file=file,
        )

    async def _execute_material_ingest_job(
        self,
        *,
        job_id: UUID,
        material: ClassroomMaterial,
        classroom_id: UUID,
        file: File | None,
    ) -> None:
        if self.material_ingest_port is None:
            return

        try:
            ingest_request = await self._build_material_ingest_request(
                classroom_id=classroom_id,
                material=material,
                file=file,
            )
            ingest_result = await self.material_ingest_port.ingest_material(
                request=ingest_request
            )
            if (
                not ingest_result.scope_candidates
                and material.source_kind is ClassroomMaterialSourceKind.FILE
            ):
                raise ClassroomMaterialIngestEmptyScopeDomainException()
            await self._complete_material_ingest_job(
                job_id=job_id,
                material_id=material.id,
                scope_candidates=ingest_result.scope_candidates,
            )
        except asyncio.CancelledError:
            raise
        except ClassroomMaterialIngestEmptyScopeDomainException as exc:
            await self._fail_material_ingest_job(
                job_id=job_id,
                material_id=material.id,
                error_message=exc.message,
            )
        except ClassroomMaterialIngestDomainException as exc:
            await self._fail_material_ingest_job(
                job_id=job_id,
                material_id=material.id,
                error_message=exc.message,
            )
        except Exception:
            await self._fail_material_ingest_job(
                job_id=job_id,
                material_id=material.id,
                error_message="강의 자료 적재 중 오류가 발생했습니다.",
            )

    @transactional
    async def _complete_material_ingest_job(
        self,
        *,
        job_id: UUID,
        material_id: UUID,
        scope_candidates: list[ClassroomMaterialScopeCandidate],
    ) -> None:
        job = await self.repository.get_by_id(job_id)
        material = await self.material_repository.get_by_id(material_id)
        if job is None or material is None:
            return

        material.mark_ingest_completed(scope_candidates)
        await self.material_repository.save(material)
        job.mark_completed(
            result={
                "material_id": str(material.id),
                "ingest_status": material.ingest_status.value,
                "scope_candidate_count": len(material.scope_candidates),
            }
        )
        await self.repository.save(job)

    @transactional
    async def _fail_material_ingest_job(
        self,
        *,
        job_id: UUID,
        material_id: UUID,
        error_message: str,
    ) -> None:
        job = await self.repository.get_by_id(job_id)
        material = await self.material_repository.get_by_id(material_id)
        if job is None or material is None:
            return

        material.mark_ingest_failed(error_message)
        await self.material_repository.save(material)
        job.mark_failed(
            error_message=material.ingest_error
            or "강의 자료 적재 중 오류가 발생했습니다."
        )
        await self.repository.save(job)

    @transactional
    async def _prepare_exam_generation_job(
        self,
        job_id: UUID,
    ) -> ExamGenerationExecution | None:
        job = await self.repository.get_by_id(job_id)
        if job is None:
            return None

        exam = await self.exam_repository.get_by_id(job.target_id)
        if exam is None:
            job.mark_failed(error_message="평가를 찾을 수 없습니다.")
            await self.repository.save(job)
            return None

        exam.mark_generation_running(started_at=datetime.now(UTC))
        await self.exam_repository.save(exam)

        if self.question_generation_port is None:
            exam.mark_generation_failed(
                error_message=ExamQuestionGenerationUnavailableException().message,
                completed_at=datetime.now(UTC),
            )
            await self.exam_repository.save(exam)
            job.mark_failed(error_message=exam.generation_error or "작업 실패")
            await self.repository.save(job)
            return None

        return ExamGenerationExecution(exam=exam)

    async def _execute_exam_generation_job(
        self,
        *,
        job_id: UUID,
        exam: Exam,
    ) -> None:
        if self.question_generation_port is None:
            return

        try:
            generation_request = await self._load_exam_generation_request(
                job_id=job_id,
                exam_id=exam.id,
            )
            if generation_request is None:
                return
            drafts = await self.question_generation_port.generate_questions(
                request=generation_request
            )
            if not drafts:
                raise ExamQuestionGenerationFailedException()
            await self._complete_exam_generation_job(
                job_id=job_id,
                exam_id=exam.id,
                drafts=list(drafts),
            )
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            await self._fail_exam_generation_job(
                job_id=job_id,
                exam_id=exam.id,
                error_message=self._resolve_error_message(exc),
            )

    @transactional
    async def _complete_exam_generation_job(
        self,
        *,
        job_id: UUID,
        exam_id: UUID,
        drafts: list[GeneratedExamQuestionDraft],
    ) -> None:
        job = await self.repository.get_by_id(job_id)
        exam = await self.exam_repository.get_by_id(exam_id)
        if job is None or exam is None:
            return

        for draft in drafts:
            exam.add_question(
                question_number=draft.question_number,
                max_score=draft.max_score,
                question_type=draft.question_type,
                bloom_level=draft.bloom_level,
                difficulty=draft.difficulty,
                question_text=draft.question_text,
                intent_text=draft.intent_text,
                rubric_text=draft.rubric_text,
                answer_options=draft.answer_options,
                correct_answer_text=draft.correct_answer_text,
                source_material_ids=draft.source_material_ids,
            )
        exam.mark_generation_completed(completed_at=datetime.now(UTC))
        await self.exam_repository.save(exam)
        job.mark_completed(
            result={
                "exam_id": str(exam.id),
                "question_count": len(drafts),
            }
        )
        await self.repository.save(job)

    @transactional
    async def _fail_exam_generation_job(
        self,
        *,
        job_id: UUID,
        exam_id: UUID,
        error_message: str,
    ) -> None:
        job = await self.repository.get_by_id(job_id)
        exam = await self.exam_repository.get_by_id(exam_id)
        if job is None or exam is None:
            return

        exam.mark_generation_failed(
            error_message=error_message,
            completed_at=datetime.now(UTC),
        )
        await self.exam_repository.save(exam)
        job.mark_failed(error_message=exam.generation_error or "작업 실패")
        await self.repository.save(job)

    @transactional
    async def _prepare_exam_result_evaluation_job(
        self,
        job_id: UUID,
    ) -> ExamResultEvaluationExecution | None:
        job = await self.repository.get_by_id(job_id)
        if job is None:
            return None

        if (
            self.exam_session_repository is None
            or self.exam_result_repository is None
            or self.exam_turn_repository is None
        ):
            job.mark_failed(
                error_message=(
                    "평가 결과 자동 채점 기능을 현재 사용할 수 없습니다."
                )
            )
            await self.repository.save(job)
            return None

        invalid_evaluation_payload_message = (
            "평가 결과 자동 채점 요청 payload가 올바르지 않습니다."
        )
        exam_id = self._get_uuid_payload_value(
            payload=job.payload,
            key="exam_id",
            error_message=invalid_evaluation_payload_message,
        )
        session_id = self._get_uuid_payload_value(
            payload=job.payload,
            key="session_id",
            error_message=invalid_evaluation_payload_message,
        )
        student_id = self._get_uuid_payload_value(
            payload=job.payload,
            key="student_id",
            error_message=invalid_evaluation_payload_message,
        )

        exam = await self.exam_repository.get_by_id(exam_id)
        if exam is None:
            job.mark_failed(error_message="평가를 찾을 수 없습니다.")
            await self.repository.save(job)
            return None

        session = await self.exam_session_repository.get_by_id(session_id)
        if session is None:
            job.mark_failed(error_message="평가 세션을 찾을 수 없습니다.")
            await self.repository.save(job)
            return None

        result_repository = self.exam_result_repository
        results = await result_repository.list_by_exam_and_student_for_update(
            exam_id=exam.id,
            student_id=student_id,
        )
        result = exam.find_result_for_session(
            results=results, session_id=session.id
        )
        return ExamResultEvaluationExecution(
            exam=exam,
            session_id=session.id,
            student_id=student_id,
            result=result,
        )

    async def _execute_exam_result_evaluation_job(
        self,
        *,
        job_id: UUID,
        exam: Exam,
        session_id: UUID,
        student_id: UUID,
        result: ExamResult,
    ) -> None:
        if (
            self.exam_session_repository is None
            or self.exam_result_repository is None
            or self.exam_turn_repository is None
        ):
            return

        if result.status is ExamResultStatus.COMPLETED:
            await self._complete_exam_result_evaluation_job_without_evaluation(
                job_id=job_id,
                exam_id=exam.id,
                session_id=session_id,
                student_id=student_id,
                result_id=result.id,
            )
            return

        evaluation_request = await self._load_exam_result_evaluation_request(
            exam=exam,
            session_id=session_id,
            student_id=student_id,
        )
        evaluation_result = await self._evaluate_exam_result(
            request=evaluation_request
        )
        await self._complete_exam_result_evaluation_job(
            job_id=job_id,
            result_id=result.id,
            exam_id=exam.id,
            session_id=session_id,
            student_id=student_id,
            evaluation_result=evaluation_result,
        )

    @transactional
    async def _complete_exam_result_evaluation_job_without_evaluation(
        self,
        *,
        job_id: UUID,
        exam_id: UUID,
        session_id: UUID,
        student_id: UUID,
        result_id: UUID,
    ) -> None:
        if self.exam_result_repository is None:
            return

        job = await self.repository.get_by_id(job_id)
        if job is None:
            return

        exam = await self.exam_repository.get_by_id(exam_id)
        if exam is None:
            raise ValueError("평가 시험을 찾을 수 없습니다.")

        result_repository = self.exam_result_repository
        results = await result_repository.list_by_exam_and_student_for_update(
            exam_id=exam_id,
            student_id=student_id,
        )
        result = exam.find_result_for_session(
            results=results, session_id=session_id
        )
        if result.id != result_id:
            raise ValueError(
                "평가 결과를 다시 확인하는 중 불일치가 발생했습니다."
            )
        job.mark_completed(
            result={
                "exam_id": str(exam_id),
                "session_id": str(session_id),
                "result_id": str(result.id),
                "status": result.status.value,
            }
        )
        await self.repository.save(job)

    @transactional
    async def _complete_exam_result_evaluation_job(
        self,
        *,
        job_id: UUID,
        result_id: UUID,
        exam_id: UUID,
        session_id: UUID,
        student_id: UUID,
        evaluation_result,
    ) -> None:
        if self.exam_result_repository is None:
            return

        job = await self.repository.get_by_id(job_id)
        if job is None:
            return

        exam = await self.exam_repository.get_by_id(exam_id)
        if exam is None:
            raise ValueError("평가 시험을 찾을 수 없습니다.")

        result_repository = self.exam_result_repository
        results = await result_repository.list_by_exam_and_student_for_update(
            exam_id=exam_id,
            student_id=student_id,
        )
        result = exam.find_result_for_session(
            results=results, session_id=session_id
        )
        if result.id != result_id:
            raise ValueError(
                "평가 결과를 다시 확인하는 중 불일치가 발생했습니다."
            )
        if result.status is ExamResultStatus.COMPLETED:
            job.mark_completed(
                result={
                    "exam_id": str(exam_id),
                    "session_id": str(session_id),
                    "result_id": str(result.id),
                    "status": result.status.value,
                }
            )
            await self.repository.save(job)
            return

        result.finalize_from_evaluation(
            summary=evaluation_result.summary,
            strengths=evaluation_result.strengths,
            weaknesses=evaluation_result.weaknesses,
            improvement_suggestions=evaluation_result.improvement_suggestions,
            criteria_results=[
                ExamResultCriterion(
                    criterion_id=item.criterion_id,
                    score=item.score,
                    feedback=item.feedback,
                )
                for item in evaluation_result.criteria_results
            ],
            criteria=exam.criteria,
        )
        await self.exam_result_repository.save(result)
        job.mark_completed(
            result={
                "exam_id": str(exam_id),
                "session_id": str(session_id),
                "result_id": str(result.id),
                "status": result.status.value,
            }
        )
        await self.repository.save(job)

    @transactional
    async def _load_exam_result_evaluation_request(
        self,
        *,
        exam: Exam,
        session_id: UUID,
        student_id: UUID,
    ) -> EvaluateExamResultRequest:
        if (
            self.exam_session_repository is None
            or self.exam_turn_repository is None
        ):
            raise ValueError(
                "평가 결과 자동 채점 기능을 현재 사용할 수 없습니다."
            )

        session = await self.exam_session_repository.get_by_id(session_id)
        if session is None:
            raise ValueError("평가 세션을 찾을 수 없습니다.")
        turns = await self.exam_turn_repository.list_by_session(
            session_id=session.id
        )
        return EvaluateExamResultRequest(
            exam_id=exam.id,
            session_id=session.id,
            student_id=student_id,
            exam_title=exam.title,
            exam_type=exam.exam_type,
            criteria=[
                ExamResultEvaluationCriterion(
                    criterion_id=criterion.id,
                    title=criterion.title,
                    weight=criterion.weight,
                    description=criterion.description,
                    excellent_definition=criterion.excellent_definition,
                    average_definition=criterion.average_definition,
                    poor_definition=criterion.poor_definition,
                )
                for criterion in exam.criteria
            ],
            questions=[
                ExamResultEvaluationQuestion(
                    question_number=question.question_number,
                    max_score=question.max_score,
                    question_type=question.question_type,
                    difficulty=question.difficulty,
                    question_text=question.question_text,
                    intent_text=question.intent_text,
                    rubric_text=question.rubric_text,
                    answer_options=list(question.answer_options),
                    correct_answer_text=question.correct_answer_text,
                )
                for question in exam.questions
            ],
            turns=[
                ExamResultEvaluationTurn(
                    sequence=turn.sequence,
                    role=turn.role,
                    event_type=turn.event_type,
                    content=turn.content,
                    metadata=dict(turn.metadata),
                )
                for turn in turns
            ],
        )

    @transactional
    async def _load_exam_generation_request(
        self,
        *,
        job_id: UUID,
        exam_id: UUID,
    ) -> GenerateExamQuestionsRequest | None:
        job = await self.repository.get_by_id(job_id)
        exam = await self.exam_repository.get_by_id(exam_id)
        if job is None or exam is None:
            return None
        return await self._build_exam_generation_request(
            exam=exam,
            payload=job.payload,
        )

    async def _build_exam_generation_request(
        self,
        *,
        exam,
        payload: dict[str, object],
    ) -> GenerateExamQuestionsRequest:
        request_payload = payload.get("request")
        if not isinstance(request_payload, dict):
            raise ExamQuestionGenerationFailedException(
                message="문항 생성 요청 payload가 올바르지 않습니다."
            )

        classroom_id = UUID(str(payload["classroom_id"]))
        source_material_ids = [
            UUID(str(material_id))
            for material_id in request_payload.get("source_material_ids", [])
        ]
        material_map = await self._get_selected_material_map(
            classroom_id=classroom_id,
            source_material_ids=source_material_ids,
        )

        return GenerateExamQuestionsRequest(
            exam_id=exam.id,
            classroom_id=classroom_id,
            title=exam.title,
            exam_type=exam.exam_type,
            scope_text=str(request_payload["scope_text"]),
            max_follow_ups=int(request_payload["max_follow_ups"]),
            difficulty=ExamDifficulty(str(request_payload["difficulty"])),
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
                    bloom_level=BloomLevel(str(item["bloom_level"])),
                    count=int(item["count"]),
                )
                for item in request_payload.get("bloom_counts", [])
            ],
            question_type_counts=[
                ExamQuestionGenerationTypeCount(
                    question_type=ExamQuestionType(str(item["question_type"])),
                    count=int(item["count"]),
                )
                for item in request_payload.get("question_type_counts", [])
            ],
            source_materials=[
                ExamQuestionSourceMaterial(
                    material_id=material_id,
                    file_name=self._resolve_material_file_name(
                        material=material_map[material_id]["material"],
                        file=material_map[material_id]["file"],
                    ),
                    title=material_map[material_id]["material"].title,
                    week=material_map[material_id]["material"].week,
                )
                for material_id in source_material_ids
            ],
        )

    async def _get_selected_material_map(
        self,
        *,
        classroom_id: UUID,
        source_material_ids: list[UUID],
    ) -> dict[UUID, dict[str, object]]:
        if not source_material_ids:
            return {}

        materials = await self.material_repository.list_by_classroom(
            classroom_id
        )
        selected_materials_by_id = {
            material.id: material
            for material in materials
            if material.id in source_material_ids
        }

        missing_material_ids = set(source_material_ids) - set(
            selected_materials_by_id
        )
        if missing_material_ids:
            raise ExamQuestionGenerationMaterialNotFoundException()

        selected_materials = [
            selected_materials_by_id[material_id]
            for material_id in source_material_ids
        ]
        if any(
            material.ingest_status is ClassroomMaterialIngestStatus.FAILED
            for material in selected_materials
        ):
            raise ExamQuestionGenerationMaterialIngestFailedException()
        if any(
            material.ingest_status
            is not ClassroomMaterialIngestStatus.COMPLETED
            for material in selected_materials
        ):
            raise ExamQuestionGenerationMaterialNotReadyException()

        material_map: dict[UUID, dict[str, object]] = {}
        for material in selected_materials:
            file = await self._load_material_file(material.file_id)
            material_map[material.id] = {
                "material": material,
                "file": file,
            }
        return material_map

    async def _load_material_file(self, file_id: UUID | None) -> File | None:
        if file_id is None:
            return None
        return await self.file_usecase.get_file(file_id)

    def _get_uuid_payload_value(
        self,
        *,
        payload: dict[str, object],
        key: str,
        error_message: str,
    ) -> UUID:
        value = payload.get(key)
        if not isinstance(value, str):
            raise ValueError(error_message)
        try:
            return UUID(value)
        except ValueError as exc:
            raise ValueError(error_message) from exc

    @transactional
    async def _fail_job(
        self,
        *,
        job_id: UUID,
        error_message: str,
    ) -> None:
        job = await self.repository.get_by_id(job_id)
        if job is None:
            return
        job.mark_failed(error_message=error_message)
        await self.repository.save(job)

    async def _evaluate_exam_result(
        self,
        *,
        request: EvaluateExamResultRequest,
    ) -> EvaluateExamResult:
        objective_questions = [
            question
            for question in request.questions
            if question.question_type
            in (
                ExamQuestionType.MULTIPLE_CHOICE,
                ExamQuestionType.SUBJECTIVE,
            )
        ]
        oral_questions = [
            question
            for question in request.questions
            if question.question_type is ExamQuestionType.ORAL
        ]

        objective_result = self._build_objective_quantitative_result(
            request=request,
            objective_questions=objective_questions,
        )

        if not oral_questions:
            return objective_result

        if self.result_evaluation_port is None:
            raise ValueError("구술형 자동 평가 기능을 현재 사용할 수 없습니다.")

        oral_request = EvaluateExamResultRequest(
            exam_id=request.exam_id,
            session_id=request.session_id,
            student_id=request.student_id,
            exam_title=request.exam_title,
            exam_type=request.exam_type,
            criteria=request.criteria,
            questions=oral_questions,
            turns=request.turns,
        )
        oral_result = await self.result_evaluation_port.evaluate_result(
            request=oral_request
        )
        return self._merge_exam_evaluation_results(
            objective_result=objective_result,
            oral_result=oral_result,
            objective_question_count=len(objective_questions),
            oral_question_count=len(oral_questions),
        )

    def _build_objective_quantitative_result(
        self,
        *,
        request: EvaluateExamResultRequest,
        objective_questions: list[ExamResultEvaluationQuestion],
    ) -> EvaluateExamResult:
        if not objective_questions:
            return EvaluateExamResult(
                summary=(
                    "객관식/주관식 문항이 없어 정량 점수 계산을 생략했습니다."
                ),
                strengths=[],
                weaknesses=[],
                improvement_suggestions=[],
                criteria_results=[],
            )

        answer_turns = self._map_answer_turns_by_question_number(request.turns)
        matched_count = 0
        total_questions = len(objective_questions)
        for question in objective_questions:
            turn = answer_turns.get(question.question_number)
            if turn is None:
                continue
            if self._is_exact_answer_match(
                expected=question.correct_answer_text,
                actual=turn.content,
            ):
                matched_count += 1

        quantitative_score = (matched_count / total_questions) * 100.0
        summary = (
            f"객관식/주관식 {total_questions}문항 중 "
            f"{matched_count}문항을 맞혀 일반 정량 점수로 반영했습니다."
        )
        strengths = []
        weaknesses = []
        improvement_suggestions = []

        if matched_count > 0:
            strengths.append(
                f"객관식/주관식에서 {matched_count}문항을 정확히 답했습니다."
            )
        if matched_count < total_questions:
            weaknesses.append(
                "객관식/주관식에서 "
                f"{total_questions - matched_count}문항이 오답 또는 "
                "무응답입니다."
            )
            improvement_suggestions.append(
                "정답형 문항은 정확한 키워드와 표현으로 다시 점검해 보세요."
            )

        feedback = (
            f"객관식/주관식 {total_questions}문항 중 "
            f"{matched_count}문항 정답으로 "
            f"{quantitative_score:.1f}점을 반영했습니다."
        )
        return EvaluateExamResult(
            summary=summary,
            strengths=strengths,
            weaknesses=weaknesses,
            improvement_suggestions=improvement_suggestions,
            criteria_results=[
                ExamResultEvaluationCriterionScore(
                    criterion_id=criterion.criterion_id,
                    score=quantitative_score,
                    feedback=feedback,
                )
                for criterion in request.criteria
            ],
        )

    def _merge_exam_evaluation_results(
        self,
        *,
        objective_result: EvaluateExamResult,
        oral_result: EvaluateExamResult,
        objective_question_count: int,
        oral_question_count: int,
    ) -> EvaluateExamResult:
        objective_scores = {
            item.criterion_id: item
            for item in objective_result.criteria_results
        }
        oral_scores = {
            item.criterion_id: item for item in oral_result.criteria_results
        }
        merged_criteria_results: list[ExamResultEvaluationCriterionScore] = []
        total_question_count = objective_question_count + oral_question_count
        criterion_ids = list(objective_scores)
        for criterion_id in oral_scores:
            if criterion_id not in objective_scores:
                criterion_ids.append(criterion_id)

        for criterion_id in criterion_ids:
            objective_item = objective_scores.get(criterion_id)
            oral_item = oral_scores.get(criterion_id)
            if objective_item is None and oral_item is not None:
                merged_criteria_results.append(oral_item)
                continue
            if oral_item is None and objective_item is not None:
                merged_criteria_results.append(objective_item)
                continue
            if objective_item is None or oral_item is None:
                continue
            if objective_question_count == 0 or total_question_count == 0:
                score = oral_item.score
                feedback = oral_item.feedback
            else:
                score = (
                    (objective_item.score * objective_question_count)
                    + (oral_item.score * oral_question_count)
                ) / total_question_count
                feedback = (
                    f"정량 점수 반영: {objective_item.feedback}\n"
                    f"구술형 평가 반영: {oral_item.feedback}"
                )
            merged_criteria_results.append(
                ExamResultEvaluationCriterionScore(
                    criterion_id=criterion_id,
                    score=score,
                    feedback=feedback,
                )
            )

        summary = oral_result.summary
        if objective_question_count > 0:
            summary = (
                f"{objective_result.summary} "
                "구술형 문항은 루브릭 평가를 함께 반영했습니다."
            )

        return EvaluateExamResult(
            summary=summary,
            strengths=[*objective_result.strengths, *oral_result.strengths],
            weaknesses=[*objective_result.weaknesses, *oral_result.weaknesses],
            improvement_suggestions=[
                *objective_result.improvement_suggestions,
                *oral_result.improvement_suggestions,
            ],
            criteria_results=merged_criteria_results,
        )

    def _map_answer_turns_by_question_number(
        self,
        turns: Iterable[ExamResultEvaluationTurn],
    ) -> dict[int, ExamResultEvaluationTurn]:
        mapped: dict[int, ExamResultEvaluationTurn] = {}
        for turn in turns:
            if turn.role is not ExamTurnRole.STUDENT:
                continue
            if turn.event_type is not ExamTurnEventType.ANSWER:
                continue
            raw_question_number = turn.metadata.get("question_number")
            if raw_question_number is None:
                continue
            try:
                question_number = int(raw_question_number)
            except ValueError:
                continue
            if question_number in mapped:
                continue
            mapped[question_number] = turn
        return mapped

    def _is_exact_answer_match(
        self, *, expected: str | None, actual: str
    ) -> bool:
        if expected is None:
            return False
        return expected.strip().casefold() == actual.strip().casefold()

    async def _build_material_ingest_request(
        self,
        *,
        classroom_id: UUID,
        material,
        file: File | None,
    ) -> ClassroomMaterialIngestRequest:
        if file is None:
            if (
                material.source_kind is not ClassroomMaterialSourceKind.LINK
                or material.source_url is None
            ):
                raise ValueError("적재 가능한 자료에 원본 정보가 없습니다.")
            validate_classroom_material_source_url(material.source_url)
            return ClassroomMaterialIngestRequest(
                material_id=material.id,
                classroom_id=classroom_id,
                title=material.title,
                week=material.week,
                description=material.description,
                source_kind=material.source_kind,
                file_name=material.source_url,
                mime_type="text/plain",
                content=material.source_url.encode(),
                source_url=material.source_url,
            )

        download = await self.file_usecase.get_file_download(file.id)
        return ClassroomMaterialIngestRequest(
            material_id=material.id,
            classroom_id=classroom_id,
            title=material.title,
            week=material.week,
            description=material.description,
            source_kind=material.source_kind,
            file_name=file.file_name,
            mime_type=file.mime_type,
            content=download.content.read(),
            source_url=material.source_url,
        )

    def _resolve_material_file_name(
        self, *, material, file: File | None
    ) -> str:
        if file is not None:
            return file.file_name
        return material.source_url or material.title

    def _resolve_error_message(self, error: Exception) -> str:
        if isinstance(error, CustomException):
            return error.message
        return "비동기 작업 처리 중 오류가 발생했습니다."
