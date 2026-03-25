from io import BytesIO
from pathlib import Path
from uuid import uuid4

import boto3

from app.file.domain.service import FileStorage, FileUploadData, StoredFile
from core.config import config


class R2FileStorage(FileStorage):
    def _client(self):
        return boto3.client(
            service_name="s3",
            endpoint_url=config.R2_ENDPOINT_URL,
            aws_access_key_id=config.R2_ACCESS_KEY_ID,
            aws_secret_access_key=config.R2_SECRET_ACCESS_KEY,
            region_name=config.R2_REGION_NAME,
        )

    async def upload(
        self,
        *,
        file_upload: FileUploadData,
        directory: str,
    ) -> StoredFile:
        key = self._build_key(
            directory=directory, file_name=file_upload.file_name
        )
        file_upload.content.seek(0)
        payload = BytesIO(file_upload.content.read())
        size = payload.getbuffer().nbytes
        payload.seek(0)

        self._client().upload_fileobj(
            payload,
            config.R2_BUCKET_NAME,
            key,
            ExtraArgs={"ContentType": file_upload.mime_type},
        )

        return StoredFile(path=key, size=size)

    async def delete(self, *, path: str) -> None:
        self._client().delete_object(Bucket=config.R2_BUCKET_NAME, Key=path)

    @staticmethod
    def _build_key(*, directory: str, file_name: str) -> str:
        suffix = Path(file_name).suffix.lower()
        return f"{directory.strip('/')}/{uuid4().hex}{suffix}"
