import hashlib
import hmac
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote

import httpx

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
        settings = get_settings()
        if not settings.tos_bucket:
            raise RuntimeError("TOS bucket is not configured")
        self.bucket = settings.tos_bucket
        self.access_key = settings.tos_access_key
        self.secret_key = settings.tos_secret_key
        self.security_token = settings.tos_session_token
        self.endpoint = settings.tos_endpoint.removeprefix("https://").removeprefix("http://").rstrip("/")
        self.region = settings.tos_region

    @staticmethod
    def _hmac(key: bytes, value: str) -> bytes:
        return hmac.new(key, value.encode(), hashlib.sha256).digest()

    def _request(self, method: str, key: str, content: bytes = b"") -> httpx.Response:
        if not self.access_key or not self.secret_key:
            raise RuntimeError("TOS credentials are not configured")
        host = f"{self.bucket}.{self.endpoint}"
        path = "/" + quote(key.lstrip("/"), safe="/~")
        now = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        payload_hash = hashlib.sha256(content).hexdigest()
        headers = {"host": host, "x-tos-date": now, "x-tos-content-sha256": payload_hash}
        if self.security_token:
            headers["x-tos-security-token"] = self.security_token
        signed_names = ";".join(sorted(headers))
        canonical_headers = "".join(f"{name}:{headers[name]}\n" for name in sorted(headers))
        canonical_request = "\n".join([method, path, "", canonical_headers, signed_names, payload_hash])
        scope = f"{now[:8]}/{self.region}/tos/request"
        string_to_sign = "\n".join(["TOS4-HMAC-SHA256", now, scope, hashlib.sha256(canonical_request.encode()).hexdigest()])
        signing_key = self._hmac(self._hmac(self._hmac(self._hmac(self.secret_key.encode(), now[:8]), self.region), "tos"), "request")
        signature = hmac.new(signing_key, string_to_sign.encode(), hashlib.sha256).hexdigest()
        headers["authorization"] = f"TOS4-HMAC-SHA256 Credential={self.access_key}/{scope}, SignedHeaders={signed_names}, Signature={signature}"
        response = httpx.request(method, f"https://{host}{path}", headers=headers, content=content, timeout=30)
        if response.status_code >= 400 and response.status_code != 404:
            raise RuntimeError(f"TOS request failed with status {response.status_code}")
        return response

    def save(self, key: str, content: bytes) -> None:
        response = self._request("PUT", key, content)
        response.raise_for_status()

    def read(self, key: str) -> bytes:
        response = self._request("GET", key)
        response.raise_for_status()
        return response.content

    def delete(self, key: str) -> None:
        response = self._request("DELETE", key)
        response.raise_for_status()

    def exists(self, key: str) -> bool:
        return self._request("HEAD", key).status_code != 404


def get_object_storage():
    return TOSStorage() if get_settings().tos_enabled else LocalStorage()
