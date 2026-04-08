"""
ReplayDetector — nonce + timestamp based replay attack prevention.

Keeps a sliding window of seen nonces and rejects:
  1. Duplicate nonces within the window
  2. Timestamps outside the allowed age range
"""
import time
import threading
from collections import deque


class ReplayDetector:
    """
    Thread-safe replay attack detector.

    Args:
        window_seconds: How long to remember nonces (default 5s).
        max_age_seconds: Maximum allowed command age (default 5s).
        min_age_seconds: Minimum allowed command age — rejects future-dated
                         commands beyond this (default 2s into future).
    """

    def __init__(
        self,
        window_seconds: float = 5.0,
        max_age_seconds: float = 5.0,
        min_age_seconds: float = 2.0,
    ):
        self._window = window_seconds
        self._max_age = max_age_seconds
        self._min_age = min_age_seconds
        self._seen: deque[tuple[str, float]] = deque()  # (nonce, expire_time)
        self._seen_set: set[str] = set()
        self._lock = threading.Lock()

    def is_replay(self, nonce: str, timestamp: float) -> bool:
        """
        Returns True if this nonce+timestamp should be rejected.
        Side effect: records the nonce on first acceptance.
        """
        now = time.time()

        # Reject stale or future-dated commands
        age = now - timestamp
        if age > self._max_age:
            return True
        if age < -self._min_age:
            return True

        with self._lock:
            self._evict_expired(now)
            if nonce in self._seen_set:
                return True
            # Accept and record
            expire = now + self._window
            self._seen.append((nonce, expire))
            self._seen_set.add(nonce)
            return False

    def _evict_expired(self, now: float) -> None:
        while self._seen and self._seen[0][1] <= now:
            old_nonce, _ = self._seen.popleft()
            self._seen_set.discard(old_nonce)

    def reset(self) -> None:
        with self._lock:
            self._seen.clear()
            self._seen_set.clear()
