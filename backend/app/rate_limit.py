import hashlib
import threading
import time
from collections import defaultdict, deque

from fastapi import Request


class SlidingWindowLimiter:
    def __init__(self) -> None:
        self._events: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def allow(self, key: str, limit: int, window_seconds: int) -> tuple[bool, int]:
        now = time.monotonic()
        with self._lock:
            events = self._events[key]
            while events and events[0] <= now - window_seconds:
                events.popleft()
            if len(events) >= limit:
                retry_after = max(1, int(window_seconds - (now - events[0])))
                return False, retry_after
            events.append(now)
            return True, 0


limiter = SlidingWindowLimiter()


def request_identity(request: Request) -> str:
    authorization = request.headers.get("authorization", "")
    if authorization:
        return hashlib.sha256(authorization.encode()).hexdigest()[:24]
    return request.client.host if request.client else "unknown"
