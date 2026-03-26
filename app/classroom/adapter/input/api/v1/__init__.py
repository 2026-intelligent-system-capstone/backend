from app.classroom.adapter.input.api.v1.classroom import (
    router as classroom_router,
)
from app.classroom.adapter.input.api.v1.material import (
    router as material_router,
)

__all__ = ["classroom_router", "material_router"]
