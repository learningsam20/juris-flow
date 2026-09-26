"""Object storage abstraction: local filesystem (dev) or GCS (prod)."""

from __future__ import annotations

from io import BytesIO
from pathlib import Path

from app.config import get_settings
from app.core.errors import JurisLabError


class StorageBackend:
    name = "local"

    def store(self, key: str, content: bytes) -> str:
        raise NotImplementedError

    def read(self, key: str) -> bytes:
        raise NotImplementedError

    def delete(self, key: str) -> None:
        raise NotImplementedError


class LocalStorage(StorageBackend):
    name = "local"

    def __init__(self, root: str = "") -> None:
        settings = get_settings()
        self.root = Path(root or settings.upload_dir)
        self.root.mkdir(parents=True, exist_ok=True)

    def store(self, key: str, content: bytes) -> str:
        path = self.root / key
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
        return str(path)

    def read(self, key: str) -> bytes:
        path = self.root / key
        if not path.exists():
            raise JurisLabError(f"Stored object not found: {key}")
        return path.read_bytes()

    def delete(self, key: str) -> None:
        (self.root / key).unlink(missing_ok=True)


class GCSStorage(StorageBackend):
    name = "gcs"

    def __init__(self, bucket: str = "") -> None:
        from app.config import get_settings

        settings = get_settings()
        self.bucket_name = bucket or settings.document_bucket
        if not self.bucket_name:
            raise JurisLabError("JAIL_DOCUMENT_BUCKET must be set for GCS storage")

    def store(self, key: str, content: bytes) -> str:
        from google.cloud import (
            storage,  # type: ignore[import-not-found,import-untyped]
        )

        client = storage.Client()
        blob = client.bucket(self.bucket_name).blob(key)
        blob.upload_from_file(BytesIO(content))
        return key

    def read(self, key: str) -> bytes:
        from google.cloud import (
            storage,  # type: ignore[import-not-found,import-untyped]
        )

        client = storage.Client()
        blob = client.bucket(self.bucket_name).blob(key)
        return blob.download_as_bytes()

    def delete(self, key: str) -> None:
        from google.cloud import storage  # type: ignore[import-not-found]

        client = storage.Client()
        blob = client.bucket(self.bucket_name).blob(key)
        blob.delete()


def get_storage() -> StorageBackend:
    from app.config import get_settings

    settings = get_settings()
    if settings.storage_backend == "gcs":
        return GCSStorage()
    return LocalStorage()
