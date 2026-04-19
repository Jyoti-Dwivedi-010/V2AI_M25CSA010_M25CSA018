from __future__ import annotations

import logging
from pathlib import Path

from app.config import load_settings

try:
    from minio import Minio
except ImportError:  # pragma: no cover - optional runtime dependency
    Minio = None

logger = logging.getLogger(__name__)


class MinIOArtifactStore:
    def __init__(self) -> None:
        settings = load_settings()

        self.enabled = bool(
            Minio is not None
            and settings.minio_endpoint
            and settings.minio_access_key
            and settings.minio_secret_key
            and settings.minio_bucket
        )

        self.bucket = settings.minio_bucket
        self.client = None

        if not self.enabled:
            return

        self.client = Minio(
            settings.minio_endpoint,
            access_key=settings.minio_access_key,
            secret_key=settings.minio_secret_key,
            secure=settings.minio_secure,
        )

        found = self.client.bucket_exists(self.bucket)
        if not found:
            self.client.make_bucket(self.bucket)

    def upload_file(self, local_path: Path, object_name: str) -> str | None:
        if not self.enabled or self.client is None:
            return None

        local_path = local_path.resolve()
        if not local_path.exists():
            raise FileNotFoundError(f"Cannot upload missing file: {local_path}")

        self.client.fput_object(self.bucket, object_name, str(local_path))
        logger.info("Uploaded artifact to MinIO bucket=%s object=%s", self.bucket, object_name)
        return f"s3://{self.bucket}/{object_name}"
