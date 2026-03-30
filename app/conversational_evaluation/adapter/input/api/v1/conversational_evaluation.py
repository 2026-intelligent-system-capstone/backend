from fastapi import APIRouter, Depends, status
from dependency_injector.wiring import inject, Provide

from app.conversational_evaluation.adapter.input.api.v1.request.exam_generation_request import ExamGenerationRequest
from app.conversational_evaluation.adapter.input.api.v1.response.exam_generation_response import ExamGenerationResponse
from app.conversational_evaluation.application.service.exam_generation_service import ExamGenerationService
from app.conversational_evaluation.container import ConversationalEvaluationContainer

router = APIRouter(prefix="/v1/evaluation", tags=["Evaluation"])

@router.post(
    "/generate",
    response_model=ExamGenerationResponse,
    status_code=status.HTTP_201_CREATED,
    summary="AI 기반 평가 문제 생성"
)
@inject
async def generate_exam(
    request: ExamGenerationRequest,
    service: ExamGenerationService = Depends(Provide[ConversationalEvaluationContainer.exam_generation_service])
):
    """
    교수자가 설정한 조건(과목, 범위, 난이도 등)에 맞춰 AI가 문제를 생성합니다.
    """
    return await service.generate_exam(request)