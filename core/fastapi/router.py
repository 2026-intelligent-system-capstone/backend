from fastapi import APIRouter

from app.auth.adapter.input.api.v1.auth import router as auth_router
from app.classroom.adapter.input.api.v1.classroom import (
    router as classroom_router,
)
from app.classroom.adapter.input.api.v1.material import (
    router as classroom_material_router,
)
from app.exam.adapter.input.api.v1.exam import router as exam_router
from app.file.adapter.input.api.v1.file import router as file_router
from app.organization.adapter.input.api.v1.organization import (
    router as organization_router,
)
from app.user.adapter.input.api.v1.user import router as user_router
from core.config import config
from core.fastapi import ExtendedFastAPI


def register_routers(app: ExtendedFastAPI):
    api_router = APIRouter(prefix=config.API_PREFIX)

    @api_router.get("/healthz", tags=["common"])
    async def healthz():
        return {"status": "ok"}

    api_router.include_router(auth_router)
    api_router.include_router(classroom_router)
    api_router.include_router(classroom_material_router)
    api_router.include_router(exam_router)
    api_router.include_router(file_router)
    api_router.include_router(organization_router)
    api_router.include_router(user_router)
    app.include_router(api_router)
