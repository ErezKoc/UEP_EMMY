"""Object storage abstraction.

`StorageService` mirrors the subset of the S3 API the platform needs, so the
local implementation can be replaced by a boto3-backed one without touching
any caller: only the dependency wiring in `get_storage_service` changes.
"""

import json
import mimetypes
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path

from app.core.config import get_settings


@dataclass(frozen=True)
class StoredObject:
    bucket: str
    key: str
    size: int
    content_type: str
    url: str

    @property
    def s3_uri(self) -> str:
        return f"s3://{self.bucket}/{self.key}"


class StorageService(ABC):
    @abstractmethod
    def put_object(self, key: str, data: bytes, content_type: str) -> StoredObject:
        """Store raw bytes under `key` and return object metadata."""

    @abstractmethod
    def get_object(self, key: str) -> bytes:
        """Return the raw bytes stored under `key`. Raises KeyError if absent."""

    @abstractmethod
    def delete_object(self, key: str) -> None:
        """Remove the object under `key` (no error if it does not exist)."""

    @abstractmethod
    def object_url(self, key: str) -> str:
        """Return a URL a browser can use to fetch the object."""

    def build_key(self, prefix: str, original_filename: str) -> str:
        """Generate a collision-free, date-partitioned key, S3-convention style."""
        extension = Path(original_filename).suffix.lower() or ".bin"
        today = datetime.now(timezone.utc).strftime("%Y/%m/%d")
        return f"{prefix}/{today}/{uuid.uuid4().hex}{extension}"


class LocalS3Storage(StorageService):
    """Filesystem-backed stand-in for an S3 bucket.

    Layout: `<root>/<bucket>/<key>` with a `<key>.meta.json` sidecar holding
    the metadata S3 would keep (content type, size, upload timestamp). Objects
    are served over HTTP by the FastAPI static mount at `/media`.
    """

    META_SUFFIX = ".meta.json"

    def __init__(self, root: str, bucket: str, public_base_url: str = "/media") -> None:
        self.bucket = bucket
        self.bucket_dir = Path(root) / bucket
        self.bucket_dir.mkdir(parents=True, exist_ok=True)
        self.public_base_url = public_base_url.rstrip("/")

    def _path_for(self, key: str) -> Path:
        path = (self.bucket_dir / key).resolve()
        if not path.is_relative_to(self.bucket_dir.resolve()):
            raise ValueError(f"Key escapes bucket root: {key!r}")
        return path

    def put_object(self, key: str, data: bytes, content_type: str) -> StoredObject:
        path = self._path_for(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)

        metadata = {
            "content_type": content_type,
            "size": len(data),
            "uploaded_at": datetime.now(timezone.utc).isoformat(),
        }
        path.with_name(path.name + self.META_SUFFIX).write_text(json.dumps(metadata))

        return StoredObject(
            bucket=self.bucket,
            key=key,
            size=len(data),
            content_type=content_type,
            url=self.object_url(key),
        )

    def get_object(self, key: str) -> bytes:
        path = self._path_for(key)
        if not path.is_file():
            raise KeyError(f"No such object: {self.bucket}/{key}")
        return path.read_bytes()

    def delete_object(self, key: str) -> None:
        path = self._path_for(key)
        path.unlink(missing_ok=True)
        path.with_name(path.name + self.META_SUFFIX).unlink(missing_ok=True)

    def object_url(self, key: str) -> str:
        return f"{self.public_base_url}/{key}"

    @staticmethod
    def guess_content_type(filename: str) -> str:
        return mimetypes.guess_type(filename)[0] or "application/octet-stream"


@lru_cache
def get_storage_service() -> StorageService:
    settings = get_settings()
    return LocalS3Storage(root=settings.storage_root, bucket=settings.storage_bucket)
