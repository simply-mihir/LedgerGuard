"""Per-client token-bucket rate limiting for the whole API (in-process).

Login already has its own progressive throttling; this bounds every other route so a single
client (or a stolen credential) cannot hammer the API or the database. Writes get a tighter
bucket than reads. A client is identified by its network peer, or by the right-most
``X-Forwarded-For`` entry when the peer is a configured trusted proxy.

Limits are per process: with N workers the effective limit is N times higher, and behind a
proxy that hides client addresses all clients share one bucket. For hard limits, also enforce
them at the reverse proxy (see docs/deployment.md).
"""

from __future__ import annotations

import threading
import time
from collections import OrderedDict
from collections.abc import Callable

from starlette.responses import JSONResponse, Response
from starlette.types import ASGIApp, Receive, Scope, Send

from ledgerguard.config import settings

_SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}
_EXEMPT_PATHS = {"/health"}
_MAX_TRACKED_CLIENTS = 10_000


class TokenBuckets:
    """Thread-safe buckets keyed by (client, kind); least-recently-used keys are evicted."""

    def __init__(self, clock: Callable[[], float] = time.monotonic) -> None:
        self._clock = clock
        self._lock = threading.Lock()
        self._state: OrderedDict[tuple[str, str], tuple[float, float]] = OrderedDict()

    def take(self, key: tuple[str, str], per_minute: int) -> float:
        """Consume one token. Returns 0.0 when allowed, else seconds until a token is free."""
        if per_minute <= 0:
            return 0.0
        rate = per_minute / 60.0
        now = self._clock()
        with self._lock:
            tokens, last = self._state.pop(key, (float(per_minute), now))
            tokens = min(float(per_minute), tokens + (now - last) * rate)
            allowed = tokens >= 1.0
            if allowed:
                tokens -= 1.0
            self._state[key] = (tokens, now)
            while len(self._state) > _MAX_TRACKED_CLIENTS:
                self._state.popitem(last=False)
            return 0.0 if allowed else (1.0 - tokens) / rate


def client_key(scope: Scope) -> str:
    peer = (scope.get("client") or ("unknown", 0))[0]
    if peer in settings.get_trusted_proxies():
        for name, value in scope.get("headers", []):
            if name == b"x-forwarded-for":
                parts = [p.strip() for p in value.decode("latin-1").split(",") if p.strip()]
                if parts:
                    return str(parts[-1])
    return str(peer)


class RateLimitMiddleware:
    def __init__(self, app: ASGIApp, buckets: TokenBuckets | None = None) -> None:
        self.app = app
        self.buckets = buckets or TokenBuckets()

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or scope["path"] in _EXEMPT_PATHS:
            await self.app(scope, receive, send)
            return
        write = scope["method"] not in _SAFE_METHODS
        limit = settings.write_rate_limit_per_minute if write else settings.rate_limit_per_minute
        wait = self.buckets.take((client_key(scope), "w" if write else "r"), limit)
        if wait > 0.0:
            response: Response = JSONResponse(
                {"detail": "Rate limit exceeded. Retry later."},
                status_code=429,
                headers={"Retry-After": str(max(1, int(wait + 0.999)))},
            )
            await response(scope, receive, send)
            return
        await self.app(scope, receive, send)


__all__ = ["RateLimitMiddleware", "TokenBuckets", "client_key"]
