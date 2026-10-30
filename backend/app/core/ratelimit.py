import threading
import time
from collections import defaultdict, deque

from fastapi import HTTPException


class FailureLimiter:
    """Counts failed attempts per key inside a sliding time window.

    In memory only, so it resets on restart and is per process. That is fine
    for a single instance; use Redis if you ever run several workers.
    """

    def __init__(self, max_attempts: int, window_seconds: int):
        self.max_attempts = max_attempts
        self.window = window_seconds
        self._hits: dict[str, deque] = defaultdict(deque)
        self._lock = threading.Lock()

    def _prune(self, key: str, now: float) -> deque:
        q = self._hits[key]
        while q and now - q[0] > self.window:
            q.popleft()
        return q

    def check(self, key: str) -> None:
        with self._lock:
            q = self._prune(key, time.time())
            if len(q) >= self.max_attempts:
                raise HTTPException(
                    status_code=429,
                    detail="Too many failed attempts. Please wait a few minutes and try again.",
                )

    def hit(self, key: str) -> None:
        with self._lock:
            now = time.time()
            self._prune(key, now).append(now)

    def reset(self, key: str) -> None:
        with self._lock:
            self._hits.pop(key, None)

    def clear_all(self) -> None:
        with self._lock:
            self._hits.clear()
