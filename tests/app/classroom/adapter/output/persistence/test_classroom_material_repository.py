from sqlalchemy.sql.sqltypes import Enum as SQLAlchemyEnum

from app.classroom.domain.entity.classroom_material import (
    ClassroomMaterialIngestStatus,
)
from core.db.sqlalchemy.models.classroom_material import (
    classroom_material_table,
)


def assert_enum_column(column, enum_class):
    assert isinstance(column.type, SQLAlchemyEnum)
    assert column.type.enum_class is enum_class
    assert column.type.native_enum is False
    assert column.type.validate_strings is True
    assert column.type.enums == [
        member.value for member in enum_class
    ]


def test_classroom_material_table_uses_non_native_enum_values():
    assert_enum_column(
        classroom_material_table.c.ingest_status,
        ClassroomMaterialIngestStatus,
    )
