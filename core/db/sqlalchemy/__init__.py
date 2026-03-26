from .mapping.classroom import init_classroom_mappers
from .mapping.classroom_material import init_classroom_material_mappers
from .mapping.exam import init_exam_mappers
from .mapping.file import init_file_mappers
from .mapping.organization import init_organization_mappers
from .mapping.user import init_user_mappers

_mappers_initialized = False


def init_orm_mappers():
    global _mappers_initialized

    if _mappers_initialized:
        return

    init_classroom_mappers()
    init_classroom_material_mappers()
    init_exam_mappers()
    init_organization_mappers()
    init_user_mappers()
    init_file_mappers()
    _mappers_initialized = True
