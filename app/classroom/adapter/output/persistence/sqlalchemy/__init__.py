from app.classroom.adapter.output.persistence.sqlalchemy.classroom import (
    ClassroomSQLAlchemyRepository,
)
from app.classroom.adapter.output.persistence.sqlalchemy.material import (
    ClassroomMaterialSQLAlchemyRepository,
)

__all__ = [
    "ClassroomSQLAlchemyRepository",
    "ClassroomMaterialSQLAlchemyRepository",
]
