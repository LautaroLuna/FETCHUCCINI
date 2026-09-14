from __future__ import annotations

import threading
import time

from django.conf import settings
from django.core.cache import cache

_STATUS_LOCK = threading.Lock()
_STATUS_CACHE: dict | None = None
_STATUS_CHECKED_AT = 0.0
_STATUS_TTL_SECONDS = 10.0


def cache_backend_name() -> str:
    return str(getattr(settings, "FETCHUCCINI_CACHE_BACKEND", "file"))


def _redis_ping() -> tuple[bool, str | None]:
    try:
        from django_redis import get_redis_connection

        connection = get_redis_connection("default")
        return bool(connection.ping()), None
    except Exception as exc:  # pragma: no cover - exact driver errors vary
        return False, type(exc).__name__


def cache_health(*, force: bool = False) -> dict:
    """Return a tiny, cached health snapshot without touching external stores."""
    global _STATUS_CACHE, _STATUS_CHECKED_AT

    now = time.monotonic()
    with _STATUS_LOCK:
        if not force and _STATUS_CACHE is not None and now - _STATUS_CHECKED_AT < _STATUS_TTL_SECONDS:
            return dict(_STATUS_CACHE)

        backend = cache_backend_name()
        started = time.perf_counter()
        error = None
        ok = True

        if backend == "redis":
            ok, error = _redis_ping()
        else:
            # File/locmem fallback: a set/get roundtrip verifies Django can use
            # the configured cache directory/backend without exposing data.
            probe_key = "runtime-health:v1"
            probe_value = str(time.time_ns())
            try:
                cache.set(probe_key, probe_value, timeout=15)
                ok = cache.get(probe_key) == probe_value
                cache.delete(probe_key)
                if not ok:
                    error = "cache roundtrip failed"
            except Exception as exc:  # pragma: no cover - filesystem failures are environment-specific
                ok = False
                error = type(exc).__name__

        elapsed_ms = max(0, int((time.perf_counter() - started) * 1000))
        payload = {
            "backend": backend,
            "ok": bool(ok),
            "latency_ms": elapsed_ms,
        }
        if error:
            payload["error"] = error[:180]

        _STATUS_CACHE = payload
        _STATUS_CHECKED_AT = now
        return dict(payload)
