from fastapi import APIRouter, Depends, status
from dependency_injector.wiring import inject, Provide

from app.learning_material.adapter.input.api.v1.request.material_ingest_request import MaterialIngestRequest
from app.learning_material.application.service.material_ingest_service import MaterialIngestService
from app.learning_material.container import LearningMaterialContainer

router = APIRouter(prefix="/v1/material", tags=["Learning Material"])

@router.post(
    "/ingest",
    status_code=status.HTTP_201_CREATED,
    summary="강의 자료(PDF) 벡터 DB 저장"
)
@inject
async def ingest_material(
    request: MaterialIngestRequest,
    service: MaterialIngestService = Depends(Provide[LearningMaterialContainer.material_ingest_service])
):
    """
    서버 내 특정 경로의 PDF를 읽어 벡터 DB(Qdrant)에 저장합니다.
    """
    return await service.ingest_pdf(request)