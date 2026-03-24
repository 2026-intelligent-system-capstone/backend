from .mapping.file import init_file_mappers
from .mapping.user import init_user_mappers

_mappers_initialized = False


def init_orm_mappers():
    global _mappers_initialized

    if _mappers_initialized:
        return

    init_user_mappers()
    init_file_mappers()
    _mappers_initialized = True
