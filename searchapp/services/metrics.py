from __future__ import annotations

import time

from django.core.cache import cache

_METRIC_TTL_SECONDS = 30 * 24 * 60 * 60


def _incr(key: str, amount: int = 1) -> None:
    if amount == 0:
        return
    try:
        if cache.add(key, amount, timeout=_METRIC_TTL_SECONDS):
            return
        cache.incr(key, amount)
    except Exception:
        # Metrics must never break a user search when cache/Redis is degraded.
        return


def _set(key: str, value) -> None:
    try:
        cache.set(key, value, timeout=_METRIC_TTL_SECONDS)
    except Exception:
        return


def record_store_result(
    store_key: str,
    *,
    elapsed_ms: int = 0,
    success: bool,
    source: str = "live",
    count: int = 0,
    count_request: bool = True,
) -> None:
    prefix = f"metrics:v1:store:{store_key}"
    if count_request:
        _incr(f"{prefix}:requests")
    _incr(f"{prefix}:elapsed_ms", max(0, int(elapsed_ms or 0)))
    _incr(f"{prefix}:results", max(0, int(count or 0)))
    if not success:
        _incr(f"{prefix}:errors")
        _set(f"{prefix}:last_error_at", int(time.time()))
    else:
        _set(f"{prefix}:last_success_at", int(time.time()))
    if source in {"live", "cache", "stale", "catalog", "coalesced"}:
        _incr(f"{prefix}:{source}")


def record_rate_limit(scope: str) -> None:
    _incr(f"metrics:v1:rate_limit:{scope}")


def _safe_int(value) -> int:
    try:
        return max(0, int(value or 0))
    except (TypeError, ValueError):
        return 0


def metrics_snapshot(store_keys: list[str]) -> dict:
    metric_names = (
        "requests", "errors", "elapsed_ms", "results", "live", "cache", "stale", "catalog", "coalesced",
        "last_success_at", "last_error_at",
    )
    keys = [f"metrics:v1:store:{store}:{name}" for store in store_keys for name in metric_names]
    try:
        values = cache.get_many(keys) or {}
    except Exception:
        values = {}

    stores = {}
    for store in store_keys:
        prefix = f"metrics:v1:store:{store}"
        requests = _safe_int(values.get(f"{prefix}:requests"))
        live_requests = _safe_int(values.get(f"{prefix}:live"))
        elapsed = _safe_int(values.get(f"{prefix}:elapsed_ms"))
        stores[store] = {
            "requests": requests,
            "origin_requests": live_requests,
            "errors": _safe_int(values.get(f"{prefix}:errors")),
            "avg_origin_ms": int(elapsed / live_requests) if live_requests else 0,
            "results": _safe_int(values.get(f"{prefix}:results")),
            "cache_hits": _safe_int(values.get(f"{prefix}:cache")),
            "stale_served": _safe_int(values.get(f"{prefix}:stale")),
            "catalog_hits": _safe_int(values.get(f"{prefix}:catalog")),
            "coalesced": _safe_int(values.get(f"{prefix}:coalesced")),
            "last_success_at": _safe_int(values.get(f"{prefix}:last_success_at")) or None,
            "last_error_at": _safe_int(values.get(f"{prefix}:last_error_at")) or None,
        }

    rate_keys = [f"metrics:v1:rate_limit:{scope}" for scope in ("autocomplete", "search_store", "search_cache", "search_all")]
    try:
        rate_values = cache.get_many(rate_keys) or {}
    except Exception:
        rate_values = {}
    rate_limits = {key.rsplit(":", 1)[-1]: _safe_int(rate_values.get(key)) for key in rate_keys}

    return {"stores": stores, "rate_limited": rate_limits}
