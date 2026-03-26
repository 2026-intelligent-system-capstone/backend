from app.file.adapter.output.storage.s3 import S3CompatibleFileStorage
from core.config import config


class R2FileStorage(S3CompatibleFileStorage):
    def __init__(self):
        super().__init__(
            endpoint_url=config.R2_ENDPOINT_URL,
            access_key_id=config.R2_ACCESS_KEY_ID,
            secret_access_key=config.R2_SECRET_ACCESS_KEY,
            bucket_name=config.R2_BUCKET_NAME,
            region_name=config.R2_REGION_NAME,
            addressing_style=config.S3_ADDRESSING_STYLE,
        )
