from pathlib import Path

from app.file.domain.service import (
    FileStorage,
    FileUploadData,
    StoredFile,
    StoredFileContent,
)


class LocalFileStorage(FileStorage):
    def __init__(self, *, root_directory: str):
        self.root_directory = Path(root_directory)

    async def upload(
        self,
        *,
        file_upload: FileUploadData,
        directory: str,
    ) -> StoredFile:
        relative_path = Path(directory) / file_upload.file_name
        full_path = self.root_directory / relative_path
        full_path.parent.mkdir(parents=True, exist_ok=True)
        file_upload.content.seek(0)
        content = file_upload.content.read()
        full_path.write_bytes(content)
        return StoredFile(path=str(relative_path), size=len(content))

    async def delete(self, *, path: str) -> None:
        full_path = self.root_directory / path
        if full_path.exists():
            full_path.unlink()

    async def open(self, *, path: str) -> StoredFileContent:
        full_path = self.root_directory / path
        return StoredFileContent(content=full_path.open("rb"))
