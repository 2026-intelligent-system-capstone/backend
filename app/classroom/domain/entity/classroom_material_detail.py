from dataclasses import dataclass

from app.classroom.domain.entity.classroom_material import ClassroomMaterial
from app.file.domain.entity.file import File


@dataclass(frozen=True)
class ClassroomMaterialDetail:
    material: ClassroomMaterial
    file: File
