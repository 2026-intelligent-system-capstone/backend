from uuid import UUID

from dependency_injector.wiring import Provide, inject
from fastapi import APIRouter, Depends

from app.auth.domain.entity import CurrentUser
from app.exam.adapter.input.api.v1.request import CreateExamRequest
from app.exam.adapter.input.api.v1.response import (
    ExamCriterionPayload,
    ExamListResponse,
    ExamPayload,
    ExamResponse,
    ExamResultListResponse,
    ExamResultPayload,
    ExamSessionPayload,
    ExamSessionResponse,
)
from app.exam.container import ExamContainer
from app.exam.domain.command import CreateExamCommand
from app.exam.domain.usecase import ExamUseCase
from core.fastapi.dependencies.permission import (
    IsAuthenticated,
    IsProfessorOrAdmin,
    PermissionDependency,
    get_current_user,
)

router = APIRouter(prefix="/classrooms/{classroom_id}/exams", tags=["exams"])


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
    "/{exam_id}/sessions",
    response_model=ExamSessionResponse,
    dependencies=[Depends(PermissionDependency([IsAuthenticated]))],
)
@inject
async def start_exam_session(
    classroom_id: UUID,
    exam_id: UUID,
    current_user: CurrentUser = Depends(get_current_user),
    usecase: ExamUseCase = Depends(Provide[ExamContainer.service]),
):
    result = await usecase.start_exam_session(
        classroom_id=classroom_id,
        exam_id=exam_id,
        current_user=current_user,
    )
    session = result.session
    return ExamSessionResponse(
        data=ExamSessionPayload(
            session_id=str(session.id),
            exam_id=str(session.exam_id),
            student_id=str(session.student_id),
            status=session.status.value,
            started_at=session.started_at.isoformat(),
            expires_at=(
                session.expires_at.isoformat()
                if session.expires_at is not None
                else None
            ),
            client_secret=result.client_secret,
        )
    )


@router.get(
    "/{exam_id}/results/me",
    response_model=ExamResultListResponse,
    dependencies=[Depends(PermissionDependency([IsAuthenticated]))],
)
@inject
async def list_my_exam_results(
    classroom_id: UUID,
    exam_id: UUID,
    current_user: CurrentUser = Depends(get_current_user),
    usecase: ExamUseCase = Depends(Provide[ExamContainer.service]),
):
    results = await usecase.list_my_exam_results(
        classroom_id=classroom_id,
        exam_id=exam_id,
        current_user=current_user,
    )
    return ExamResultListResponse(
        data=[_build_exam_result_payload(result) for result in results]
    )
