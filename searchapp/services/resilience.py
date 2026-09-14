from __future__ import annotations

import logging
import time
import threading
from contextlib import contextmanager

from django.conf import settings

from django.core.cache import cache

logger = logging.getLogger(__name__)

CIRCUIT_FAILURE_THRESHOLD = 3
CIRCUIT_OPEN_SECONDS = 5 * 60
CIRCUIT_STATE_SECONDS = 15 * 60


def _key(store_key: str) -> str:
    return f"store-circuit:v1:{store_key}"


def circuit_state(store_key: str) -> dict:
    state = cache.get(_key(store_key)) or {}
    try:
        failures = max(0, int(state.get("failures") or 0))
    except (TypeError, ValueError):
        failures = 0
    try:
        open_until = float(state.get("open_until") or 0)
    except (TypeError, ValueError):
        open_until = 0
    return {"failures": failures, "open_until": open_until}


def circuit_is_open(store_key: str) -> tuple[bool, int]:
    state = circuit_state(store_key)
    now = time.time()
    open_until = state["open_until"]
    if open_until > now:
        return True, max(1, int(open_until - now))
    if open_until:
        cache.delete(_key(store_key))
    return False, 0


def circuit_record_success(store_key: str) -> None:
    previous = circuit_state(store_key)
    if previous["failures"] or previous["open_until"]:
        logger.info("Circuit recovered for store=%s", store_key)
    cache.delete(_key(store_key))


def circuit_record_failure(store_key: str, error: str | None = None) -> dict:
    state = circuit_state(store_key)
    failures = state["failures"] + 1
    open_until = 0.0
    if failures >= CIRCUIT_FAILURE_THRESHOLD:
        open_until = time.time() + CIRCUIT_OPEN_SECONDS
        logger.warning(
            "Circuit opened for store=%s failures=%s error=%s",
            store_key, failures, error or "unknown",
        )
    else:
        logger.warning(
            "Store request failed store=%s failures=%s/%s error=%s",
            store_key, failures, CIRCUIT_FAILURE_THRESHOLD, error or "unknown",
        )
    payload = {"failures": failures, "open_until": open_until}
    cache.set(_key(store_key), payload, CIRCUIT_STATE_SECONDS)
    return payload


class StoreConcurrencyBusy(RuntimeError):
    pass


_GATE_LOCK = threading.Lock()
_GATE_SEMAPHORE = None
_GATE_LIMIT = None


def _store_gate():
    global _GATE_SEMAPHORE, _GATE_LIMIT
    limit = max(1, int(getattr(settings, "FETCHUCCINI_GLOBAL_STORE_CONCURRENCY", 6)))
    with _GATE_LOCK:
        if _GATE_SEMAPHORE is None or _GATE_LIMIT != limit:
            _GATE_SEMAPHORE = threading.BoundedSemaphore(limit)
            _GATE_LIMIT = limit
        return _GATE_SEMAPHORE, limit


@contextmanager
def store_request_slot():
    """Bound total outbound store work per process to protect hosted threads."""
    semaphore, limit = _store_gate()
    wait_seconds = max(1.0, float(getattr(settings, "FETCHUCCINI_STORE_GATE_WAIT_SECONDS", 20)))
    acquired = semaphore.acquire(timeout=wait_seconds)
    if not acquired:
        raise StoreConcurrencyBusy(f"limite global {limit} ocupado")
    try:
        yield
    finally:
        semaphore.release()


def store_gate_limit() -> int:
    _semaphore, limit = _store_gate()
    return limit
