"""A small in-process rate limiter for the endpoints anybody can call.

Deliberately in-memory, and deliberately not Redis. This application deploys as
a single container with a single worker; adding a shared store for a counter
that resets on restart would be more infrastructure than the thing it protects.
The trade-off is written down rather than hidden: with two instances behind a
load balancer each keeps its own counters, so the effective limit is the
configured one times the number of instances. That still turns "unlimited" into
"bounded", which is the point - this is here to stop somebody walking an email
list or hammering a mail server, not to be a billing meter.

Keys are opaque strings the caller builds. Nothing here parses or stores an
email address in a form a log could leak: the auth routes hash the address into
the key first, so the limiter holds digests rather than a list of who has tried
to sign in.
"""

from __future__ import annotations

import hashlib
import threading
import time
from collections import defaultdict, deque


class RateLimiter:
    """At most `limit` hits per `window_seconds`, per key.

    A sliding window over the hit timestamps rather than a fixed bucket: a
    fixed bucket lets somebody send twice the limit across a boundary, which
    for "send me a password reset email" means twice the mail.
    """

    def __init__(self, *, limit: int, window_seconds: float) -> None:
        self.limit = limit
        self.window_seconds = window_seconds
        self._hits: dict[str, deque[float]] = defaultdict(deque)
        # The sweep and the API can touch this from different threads (FastAPI
        # runs sync endpoints in a threadpool), and a deque is not safe to
        # mutate from two of them at once.
        self._lock = threading.Lock()

    def allow(self, key: str, *, now: float | None = None) -> bool:
        """Record a hit and say whether it is within the limit."""
        now = time.monotonic() if now is None else now
        with self._lock:
            hits = self._hits[key]
            cutoff = now - self.window_seconds
            while hits and hits[0] <= cutoff:
                hits.popleft()
            if len(hits) >= self.limit:
                return False
            hits.append(now)
            return True

    def retry_after(self, key: str, *, now: float | None = None) -> int:
        """Whole seconds until this key has room again, for the Retry-After header."""
        now = time.monotonic() if now is None else now
        with self._lock:
            hits = self._hits[key]
            if not hits:
                return 0
            return max(1, int(hits[0] + self.window_seconds - now) + 1)

    def reset(self, key: str | None = None) -> None:
        """Forget one key, or all of them. Used by tests, not by the app."""
        with self._lock:
            if key is None:
                self._hits.clear()
            else:
                self._hits.pop(key, None)


def key_for(prefix: str, value: str) -> str:
    """A limiter key that does not contain the thing it is limiting.

    The address is hashed so that a memory dump, a debugger, or a stray log of
    this dictionary is not a list of the email addresses somebody has been
    probing for.
    """
    digest = hashlib.sha256(value.strip().lower().encode()).hexdigest()[:32]
    return f"{prefix}:{digest}"
