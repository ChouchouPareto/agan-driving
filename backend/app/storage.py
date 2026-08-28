from pathlib import Path

from app.core.config import get_settings


class LocalStorage:
    def __init__(self) -> None:
        self.root = Path(get_settings().ocr_storage_dir).resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def _path(self, key: str) -> Path:
        path = (self.root / key).resolve()
        if self.root not in path.parents:
            raise ValueError("unsafe storage key")
        return path

    def save(self, key: str, content: bytes) -> None:
        self._path(key).write_bytes(content)

    def read(self, key: str) -> bytes:
        return self._path(key).read_bytes()

    def delete(self, key: str) -> None:
        self._path(key).unlink(missing_ok=True)

    def exists(self, key: str) -> bool:
        return self._path(key).exists()


class TOSStorage:
    def __init__(self) -> None:
        try:
            import tos
        except ImportError as exc:
            raise RuntimeError("TOS SDK is not installed") from exc
        settings = get_settings()
        if not settings.tos_bucket:
            raise RuntimeError("TOS bucket is not configured")
        self.bucket = settings.tos_bucket
        self.client = tos.TosClientV2(
            settings.tos_access_key,
            settings.tos_secret_key,
            settings.tos_endpoint,
            settings.tos_region,
            security_token=settings.tos_session_token or None,
        )

    def save(self, key: str, content: bytes) -> None:
        self.client.put_object(self.bucket, key, content=content)

    def read(self, key: str) -> bytes:
        response = self.client.get_object(self.bucket, key)
        return response.read()

    def delete(self, key: str) -> None:
        self.client.delete_object(self.bucket, key)

    def exists(self, key: str) -> bool:
        try:
            self.client.head_object(self.bucket, key)
            return True
        except Exception as exc:
            status_code = getattr(exc, "status_code", None)
            if status_code == 404:
                return False
            raise


def get_object_storage():
    return TOSStorage() if get_settings().tos_enabled else LocalStorage()
