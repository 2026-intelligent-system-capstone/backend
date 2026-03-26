from dataclasses import dataclass
from typing import BinaryIO

from app.file.domain.entity.file import File


@dataclass
class FileDownload:
    file: File
    content: BinaryIO

    @property
    def file_name(self) -> str:
        return self.file.file_name

    @property
    def mime_type(self) -> str:
        return self.file.mime_type
