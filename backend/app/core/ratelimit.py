"""A small in-process rate limiter for the unauthenticated link endpoints.

Deliberately not Redis: one container, one process, and the thing being protected is a
handful of emails a week. It forgets everything on restart, which is an acceptable
trade for having no moving parts. Keyed by whatever the caller passes - an email
address and the client IP are both used, so neither alone can be flooded.
"""

import time
from collections import defaultdict
from threading import Lock

from app.core.errors import AppError


class TooManyRequests(AppError):
    status_code = 429


class RateLimiter:
    def __init__(self, limit: int, per_seconds: int):
        self.limit = limit
        self.per = per_seconds
        self._hits: dict[str, list[float]] = defaultdict(list)
        self._lock = Lock()

    def check(self, key: str, message: str = "Too many attempts - try again shortly") -> None:
        now = time.monotonic()
        with self._lock:
            hits = [t for t in self._hits[key] if now - t < self.per]
            if len(hits) >= self.limit:
                self._hits[key] = hits
                raise TooManyRequests(message)
            hits.append(now)
            self._hits[key] = hits

    def clear(self, key: str) -> None:
        """Forget one key - called when an attempt succeeds, so a parent who gets their
        password right on the fourth go doesn't carry the first three around."""
        with self._lock:
            self._hits.pop(key, None)

    def reset(self) -> None:
        with self._lock:
            self._hits.clear()


# Asking for a link: generous enough for a parent who mistypes, tight enough that the
# mailbox can't be used as a weapon.
signin_links = RateLimiter(limit=5, per_seconds=15 * 60)
# Following a link: stops someone grinding tokens against the endpoint.
token_attempts = RateLimiter(limit=20, per_seconds=15 * 60)
# Guessing a password. Cyber Essentials v3.3 asks for brute-force protection and allows
# "no more than 10 guesses in 5 minutes"; throttling is preferred to locking the account,
# because a locked-out coach at the side of a pitch is a worse outcome than a slow one.
password_attempts = RateLimiter(limit=10, per_seconds=5 * 60)
