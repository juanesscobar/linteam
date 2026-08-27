from collections import defaultdict, deque
from threading import Lock
from time import monotonic


class InMemoryRateLimiter:
    """Single-process limiter; production may replace it with a shared Redis adapter."""

    def __init__(self, requests_per_minute: int) -> None:
        self.limit = requests_per_minute
        self._requests: defaultdict[str, deque[float]] = defaultdict(deque)
        self._lock = Lock()

    def allow(self, key: str) -> bool:
        now = monotonic()
        cutoff = now - 60
        with self._lock:
            values = self._requests[key]
            while values and values[0] < cutoff:
                values.popleft()
            if len(values) >= self.limit:
                return False
            values.append(now)
            return True
