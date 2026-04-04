from uuid import UUID

from dependency_injector.wiring import Provide, inject
from fastapi import APIRouter, Depends

from app.auth.domain.entity import CurrentUser
from app.exam.adapter.input.api.v1.request import (
    CompleteExamSessionRequest,
    CreateExamQuestionRequest,
    CreateExamRequest,
    FinalizeExamResultRequest,
    GenerateExamQuestionsRequest,
    RecordExamTurnRequest,
    UpdateExamQuestionRequest,
)
from app.exam.adapter.input.api.v1.response import (
    ExamCriterionPayload,
    ExamListResponse,
    ExamPayload,
    ExamQuestionListResponse,
    ExamQuestionPayload,
    ExamQuestionResponse,
    ExamResponse,
    ExamResultListResponse,
    ExamResultPayload,
    ExamResultResponse,
    ExamSessionPayload,
    ExamSessionResponse,
    ExamTurnPayload,
    ExamTurnResponse,
)
from app.exam.container import ExamContainer
from app.exam.domain.command import (
    CompleteExamSessionCommand,
    CreateExamCommand,
    CreateExamQuestionCommand,
    FinalizeExamResultCommand,
    GenerateExamQuestionsCommand,
    RecordExamTurnCommand,
    UpdateExamQuestionCommand,
)
from app.exam.domain.usecase import ExamUseCase
from core.fastapi.dependencies.permission import (
    IsAuthenticated,
    IsProfessorOrAdmin,
    PermissionDependency,
    get_current_user,
)

router = APIRouter(prefix="/classrooms/{classroom_id}/exams", tags=["exams"])
student_router = APIRouter(prefix="/exams", tags=["exams"])


def _build_exam_question_payload(question) -> ExamQuestionPayload:
    return ExamQuestionPayload(
        id=str(question.id),
        exam_id=str(question.exam_id),
        question_number=question.question_number,
        bloom_level=question.bloom_level.value,
        difficulty=question.difficulty.value,
        question_text=question.question_text,
        scope_text=question.scope_text,
        evaluation_objective=question.evaluation_objective,
        answer_key=question.answer_key,
        scoring_criteria=question.scoring_criteria,
        source_material_ids=[
            str(source_material_id)
            for source_material_id in question.source_material_ids
        ],
        status=question.status.value,
    )


def _build_exam_payload(exam) -> ExamPayload:
    return ExamPayload(
        id=str(exam.id),
        classroom_id=str(exam.classroom_id),
        title=exam.title,
        description=exam.description,
        exam_type=exam.exam_type.value,
        status=exam.status.value,
        duration_minutes=exam.duration_minutes,
        starts_at=exam.starts_at.isoformat(),
        ends_at=exam.ends_at.isoformat(),
        allow_retake=exam.allow_retake,
        week=exam.week,
        criteria=[
            ExamCriterionPayload(
                id=str(criterion.id),
                title=criterion.title,
                description=criterion.description,
                weight=criterion.weight,
                sort_order=criterion.sort_order,
                excellent_definition=criterion.excellent_definition,
                average_definition=criterion.average_definition,
                poor_definition=criterion.poor_definition,
            )
            for criterion in exam.criteria
        ],
        questions=[
            _build_exam_question_payload(question)
            for question in exam.questions
        ],
    )


def _build_exam_result_payload(result) -> ExamResultPayload:
    return ExamResultPayload(
        id=str(result.id),
        exam_id=str(result.exam_id),
        session_id=str(result.session_id),
        student_id=str(result.student_id),
        status=result.status.value,
        submitted_at=(
            result.submitted_at.isoformat()
            if result.submitted_at is not None
            else None
        ),
        overall_score=result.overall_score,
        summary=result.summary,
    )


def _build_exam_turn_payload(turn) -> ExamTurnPayload:
    return ExamTurnPayload(
        id=str(turn.id),
        session_id=str(turn.session_id),
        sequence=turn.sequence,
        role=turn.role.value,
        event_type=turn.event_type.value,
        content=turn.content,
        created_at=turn.created_at.isoformat(),
        metadata=turn.metadata,
    )


def _build_exam_session_payload(
    session,
    *,
    client_secret: str | None,
) -> ExamSessionPayload:
    ended_at = getattr(session, "ended_at", None)
    expires_at = getattr(session, "expires_at", None)
    return ExamSessionPayload(
        session_id=str(session.id),
        exam_id=str(session.exam_id),
        student_id=str(session.student_id),
        status=session.status.value,
        started_at=session.started_at.isoformat(),
        ended_at=ended_at.isoformat() if ended_at is not None else None,
        expires_at=expires_at.isoformat() if expires_at is not None else None,
        client_secret=client_secret,
    )


@router.post(
    "",
    response_model=ExamResponse,
    dependencies=[Depends(PermissionDependency([IsProfessorOrAdmin]))],
)
@inject
async def create_exam(
    classroom_id: UUID,
    request: CreateExamRequest,
    current_user: CurrentUser = Depends(get_current_user),
    usecase: ExamUseCase = Depends(Provide[ExamContainer.service]),
):
    exam = await usecase.create_exam(
        classroom_id=classroom_id,
        current_user=current_user,
        command=CreateExamCommand(**request.model_dump()),
    )
    return ExamResponse(data=_build_exam_payload(exam))


@router.get(
    "",
    response_model=ExamListResponse,
    dependencies=[Depends(PermissionDependency([IsAuthenticated]))],
)
@inject
async def list_exams(
    classroom_id: UUID,
    current_user: CurrentUser = Depends(get_current_user),
    usecase: ExamUseCase = Depends(Provide[ExamContainer.service]),
):
    exams = await usecase.list_exams(
        classroom_id=classroom_id,
        current_user=current_user,
    )
    return ExamListResponse(data=[_build_exam_payload(exam) for exam in exams])


@router.get(
    "/{exam_id}",
    response_model=ExamResponse,
    dependencies=[Depends(PermissionDependency([IsAuthenticated]))],
)
@inject
async def get_exam(
    classroom_id: UUID,
    exam_id: UUID,
    current_user: CurrentUser = Depends(get_current_user),
    usecase: ExamUseCase = Depends(Provide[ExamContainer.service]),
):
    exam = await usecase.get_exam(
        classroom_id=classroom_id,
        exam_id=exam_id,
        current_user=current_user,
    )
    return ExamResponse(data=_build_exam_payload(exam))


@router.post(
    "/{exam_id}/questions",
    response_model=ExamQuestionResponse,
    dependencies=[Depends(PermissionDependency([IsProfessorOrAdmin]))],
)
@inject
async def create_exam_question(
    classroom_id: UUID,
    exam_id: UUID,
    request: CreateExamQuestionRequest,
    current_user: CurrentUser = Depends(get_current_user),
    usecase: ExamUseCase = Depends(Provide[ExamContainer.service]),
):
    question = await usecase.create_exam_question(
        classroom_id=classroom_id,
        exam_id=exam_id,
        current_user=current_user,
        command=CreateExamQuestionCommand(**request.model_dump()),
    )
    return ExamQuestionResponse(data=_build_exam_question_payload(question))


@router.patch(
    "/{exam_id}/questions/{question_id}",
    response_model=ExamQuestionResponse,
    dependencies=[Depends(PermissionDependency([IsProfessorOrAdmin]))],
)
@inject
async def update_exam_question(
    classroom_id: UUID,
    exam_id: UUID,
    question_id: UUID,
    request: UpdateExamQuestionRequest,
    current_user: CurrentUser = Depends(get_current_user),
    usecase: ExamUseCase = Depends(Provide[ExamContainer.service]),
):
    question = await usecase.update_exam_question(
        classroom_id=classroom_id,
        exam_id=exam_id,
        question_id=question_id,
        current_user=current_user,
        command=UpdateExamQuestionCommand(
            **request.model_dump(exclude_unset=True)
        ),
    )
    return ExamQuestionResponse(data=_build_exam_question_payload(question))


@router.delete(
    "/{exam_id}/questions/{question_id}",
    response_model=ExamQuestionResponse,
    dependencies=[Depends(PermissionDependency([IsProfessorOrAdmin]))],
)
@inject
async def delete_exam_question(
    classroom_id: UUID,
    exam_id: UUID,
    question_id: UUID,
    current_user: CurrentUser = Depends(get_current_user),
    usecase: ExamUseCase = Depends(Provide[ExamContainer.service]),
):
    question = await usecase.delete_exam_question(
        classroom_id=classroom_id,
        exam_id=exam_id,
        question_id=question_id,
        current_user=current_user,
    )
    return ExamQuestionResponse(data=_build_exam_question_payload(question))


@router.post(
    "/{exam_id}/questions/generate",
    response_model=ExamQuestionListResponse,
    dependencies=[Depends(PermissionDependency([IsProfessorOrAdmin]))],
)
@inject
async def generate_exam_questions(
    classroom_id: UUID,
    exam_id: UUID,
    request: GenerateExamQuestionsRequest,
    current_user: CurrentUser = Depends(get_current_user),
    usecase: ExamUseCase = Depends(Provide[ExamContainer.service]),
):
    questions = await usecase.generate_exam_questions(
        classroom_id=classroom_id,
        exam_id=exam_id,
        current_user=current_user,
        command=GenerateExamQuestionsCommand(**request.model_dump()),
    )
    return ExamQuestionListResponse(
        data=[_build_exam_question_payload(question) for question in questions]
    )


@student_router.post(
    "/{exam_id}/sessions",
    response_model=ExamSessionResponse,
    dependencies=[Depends(PermissionDependency([IsAuthenticated]))],
)
@inject
async def start_exam_session(
    exam_id: UUID,
    current_user: CurrentUser = Depends(get_current_user),
    usecase: ExamUseCase = Depends(Provide[ExamContainer.service]),
):
    result = await usecase.start_exam_session(
        exam_id=exam_id,
        current_user=current_user,
    )
    return ExamSessionResponse(
        data=_build_exam_session_payload(
            result.session,
            client_secret=result.client_secret,
        )
    )


@student_router.get(
    "/{exam_id}/results/me",
    response_model=ExamResultListResponse,
    dependencies=[Depends(PermissionDependency([IsAuthenticated]))],
)
@inject
async def list_my_exam_results(
    exam_id: UUID,
    current_user: CurrentUser = Depends(get_current_user),
    usecase: ExamUseCase = Depends(Provide[ExamContainer.service]),
):
    results = await usecase.list_my_exam_results(
        exam_id=exam_id,
        current_user=current_user,
    )
    return ExamResultListResponse(
        data=[_build_exam_result_payload(result) for result in results]
    )


@student_router.post(
    "/{exam_id}/sessions/{session_id}/turns",
    response_model=ExamTurnResponse,
    dependencies=[Depends(PermissionDependency([IsAuthenticated]))],
)
@inject
async def record_exam_turn(
    exam_id: UUID,
    session_id: UUID,
    request: RecordExamTurnRequest,
    current_user: CurrentUser = Depends(get_current_user),
    usecase: ExamUseCase = Depends(Provide[ExamContainer.service]),
):
    turn = await usecase.record_exam_turn(
        exam_id=exam_id,
        session_id=session_id,
        current_user=current_user,
        command=RecordExamTurnCommand(**request.model_dump()),
    )
    return ExamTurnResponse(data=_build_exam_turn_payload(turn))


@student_router.post(
    "/{exam_id}/sessions/{session_id}/complete",
    response_model=ExamSessionResponse,
    dependencies=[Depends(PermissionDependency([IsAuthenticated]))],
)
@inject
async def complete_exam_session(
    exam_id: UUID,
    session_id: UUID,
    request: CompleteExamSessionRequest,
    current_user: CurrentUser = Depends(get_current_user),
    usecase: ExamUseCase = Depends(Provide[ExamContainer.service]),
):
    session = await usecase.complete_exam_session(
        exam_id=exam_id,
        session_id=session_id,
        current_user=current_user,
        command=CompleteExamSessionCommand(**request.model_dump()),
    )
    return ExamSessionResponse(
        data=_build_exam_session_payload(session, client_secret=None)
    )


@student_router.post(
    "/{exam_id}/sessions/{session_id}/results/finalize",
    response_model=ExamResultResponse,
    dependencies=[Depends(PermissionDependency([IsAuthenticated]))],
)
@inject
async def finalize_exam_result(
    exam_id: UUID,
    session_id: UUID,
    request: FinalizeExamResultRequest,
    current_user: CurrentUser = Depends(get_current_user),
    usecase: ExamUseCase = Depends(Provide[ExamContainer.service]),
):
    result = await usecase.finalize_exam_result(
        exam_id=exam_id,
        session_id=session_id,
        current_user=current_user,
        command=FinalizeExamResultCommand(**request.model_dump()),
    )
    return ExamResultResponse(data=_build_exam_result_payload(result))
