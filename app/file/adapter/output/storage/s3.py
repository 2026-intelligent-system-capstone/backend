from io import BytesIO
from pathlib import Path
from uuid import uuid4

import boto3
from botocore.config import Config as BotoConfig

from app.file.domain.service import (
    FileStorage,
    FileUploadData,
    StoredFile,
    StoredFileContent,
)


class S3CompatibleFileStorage(FileStorage):
    def __init__(
        self,
        *,
        endpoint_url: str,
        access_key_id: str,
        secret_access_key: str,
        bucket_name: str,
        region_name: str,
        addressing_style: str = "auto",
    ):
        self.endpoint_url = endpoint_url
        self.access_key_id = access_key_id
        self.secret_access_key = secret_access_key
        self.bucket_name = bucket_name
        self.region_name = region_name
        self.addressing_style = addressing_style

    def _client(self):
        return boto3.client(
            service_name="s3",
            endpoint_url=self.endpoint_url,
            aws_access_key_id=self.access_key_id,
            aws_secret_access_key=self.secret_access_key,
            region_name=self.region_name,
            config=BotoConfig(s3={"addressing_style": self.addressing_style}),
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
            self.bucket_name,
            key,
            ExtraArgs={"ContentType": file_upload.mime_type},
        )

        return StoredFile(path=key, size=size)

    async def delete(self, *, path: str) -> None:
        self._client().delete_object(Bucket=self.bucket_name, Key=path)

    async def open(self, *, path: str) -> StoredFileContent:
        response = self._client().get_object(Bucket=self.bucket_name, Key=path)
        return StoredFileContent(content=response["Body"])

    @staticmethod
    def _build_key(*, directory: str, file_name: str) -> str:
        suffix = Path(file_name).suffix.lower()
        return f"{directory.strip('/')}/{uuid4().hex}{suffix}"
