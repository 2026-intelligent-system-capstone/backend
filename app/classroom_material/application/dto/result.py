from dataclasses import dataclass

from app.classroom_material.domain.entity import ClassroomMaterial
from app.file.domain.entity.file import File


@dataclass
class ClassroomMaterialResult:
    material: ClassroomMaterial
    file: File
