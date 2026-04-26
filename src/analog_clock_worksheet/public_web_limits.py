"""Lightweight limits for an Internet-facing worksheet app (single-process friendly)."""

from __future__ import annotations

import os
import threading
import time

_SAVE_DISK_ENV = "SAVE_PDF_TO_DISK"
_RATE_ENV = "WORKSHEET_RATE_LIMIT_PER_MINUTE"


def save_pdf_to_disk() -> bool:
    """Persist each generated PDF under ``output/`` (default: yes). Set ``SAVE_PDF_TO_DISK=0`` to disable."""
    v = (os.environ.get(_SAVE_DISK_ENV) or "1").strip().lower()
    return v not in ("0", "false", "no", "off")


def rate_limit_per_minute() -> int:
    """Max POST ``/worksheet`` per client per minute; ``0`` or unset = no limit."""
    raw = (os.environ.get(_RATE_ENV) or "").strip()
    if not raw:
        return 0
    try:
        n = int(raw)
    except ValueError:
        return 0
    return max(0, n)


def client_rate_limit_key(request_scope: dict) -> str:
    """Client key for rate limiting; first hop of ``X-Forwarded-For`` when present."""
    headers = request_scope.get("headers") or []
    hmap = {k.decode().lower(): v.decode() for k, v in headers}
    xf = hmap.get("x-forwarded-for", "").strip()
    if xf:
        return xf.split(",")[0].strip() or "unknown"
    client = request_scope.get("client")
    if client and client[0]:
        return client[0]
    return "unknown"


class _FixedWindowPerMinuteLimiter:
    """Fixed 60s windows per key; thread-safe for multi-threaded workers."""

    __slots__ = ("_max", "_lock", "_state")

    def __init__(self, max_per_window: int) -> None:
        self._max = max_per_window
        self._lock = threading.Lock()
        self._state: dict[tuple[str, int], int] = {}

    def allow(self, key: str) -> bool:
        window = int(time.time() // 60)
        with self._lock:
            wk = (key, window)
            prev_w = window - 1
            for ow in list(self._state):
                if ow[0] == key and ow[1] < prev_w:
                    del self._state[ow]
            count = self._state.get(wk, 0)
            if count >= self._max:
                return False
            self._state[wk] = count + 1
            return True


_limiter: _FixedWindowPerMinuteLimiter | None = None
_limiter_lock = threading.Lock()


def rate_limit_allow(key: str) -> bool:
    """Return False if this key is over the configured per-minute cap."""
    cap = rate_limit_per_minute()
    if cap <= 0:
        return True
    global _limiter
    with _limiter_lock:
        if _limiter is None or _limiter._max != cap:
            _limiter = _FixedWindowPerMinuteLimiter(cap)
    return _limiter.allow(key)
