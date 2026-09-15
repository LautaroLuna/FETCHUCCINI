import hashlib
import logging
import json
import secrets
import time

from django.conf import settings
from django.core.cache import cache
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_POST
from django.shortcuts import render

from .services.aggregator import SearchAggregator
from .services.scryfall import ScryfallService
from .services.resilience import circuit_state, store_gate_limit
from .services.mercadia_catalog import (
    append_batch as mercadia_catalog_append_batch,
    begin_sync as mercadia_catalog_begin_sync,
    catalog_status as mercadia_catalog_status,
    catalog_status_lightweight as mercadia_catalog_health_status,
    catalog_path as mercadia_catalog_path,
    finish_sync as mercadia_catalog_finish_sync,
    search_catalog as mercadia_catalog_search,
)
from .services.listing_normalization import dedupe_listing_dicts, normalize_listing_dict
from .services.cache_runtime import cache_health
from .services.metrics import metrics_snapshot, record_rate_limit, record_store_result
from .services.utils import normalize_card_search_text


FRESH_CACHE_SECONDS = 5 * 60
MAGICDEALERS_FRESH_CACHE_SECONDS = 30 * 60
STALE_CACHE_SECONDS = 24 * 60 * 60
AUTOCOMPLETE_CACHE_SECONDS = 60 * 60

MERCADIA_BRIDGE_SYNC_SECONDS = 30 * 60
MERCADIA_BRIDGE_FRESH_SECONDS = 40 * 60
MERCADIA_BRIDGE_STALE_SECONDS = 7 * 24 * 60 * 60
MERCADIA_BRIDGE_PENDING_SECONDS = 7 * 24 * 60 * 60
MERCADIA_BRIDGE_ACTIVE_SECONDS = 7 * 24 * 60 * 60
MERCADIA_BRIDGE_PENDING_KEY = "mercadia-bridge:v3:pending"

logger = logging.getLogger(__name__)
_APP_STARTED_AT = time.time()

RATE_LIMITS = {
    "autocomplete": (90, 60),
    "search_store": (90, 60),
    "search_cache": (60, 60),
    "search_all": (15, 60),
}


def _client_ip(request) -> str:
    # Railway exposes the original remote address as X-Real-IP. Keep
    # X-Forwarded-For/REMOTE_ADDR fallbacks for Render and local development.
    real_ip = (request.META.get("HTTP_X_REAL_IP") or "").strip()
    if real_ip:
        return real_ip
    forwarded = [part.strip() for part in (request.META.get("HTTP_X_FORWARDED_FOR") or "").split(",") if part.strip()]
    if forwarded:
        return forwarded[0]
    return request.META.get("REMOTE_ADDR") or "unknown"


def _rate_limit_response(request, scope: str):
    limit, window = RATE_LIMITS[scope]
    now = int(time.time())
    bucket = now // window
    identity = _client_ip(request)
    digest = hashlib.sha256(identity.encode("utf-8")).hexdigest()[:24]
    key = f"rate:v1:{scope}:{digest}:{bucket}"
    try:
        if cache.add(key, 1, timeout=window + 5):
            count = 1
        else:
            try:
                count = cache.incr(key)
            except ValueError:
                cache.set(key, 1, timeout=window + 5)
                count = 1
    except Exception as exc:
        # Rate limiting must fail open if the cache backend is temporarily
        # unavailable; /health/ will report the degraded cache separately.
        logger.warning("Rate limit cache unavailable scope=%s error=%s", scope, type(exc).__name__)
        return None
    if not isinstance(count, int) or count <= limit:
        return None
    retry_after = max(1, window - (now % window))
    record_rate_limit(scope)
    logger.warning("Rate limit exceeded scope=%s ip_hash=%s count=%s", scope, digest, count)
    response = JsonResponse({
        "error": "Demasiadas búsquedas en poco tiempo. Probá de nuevo en unos segundos.",
        "retry_after_seconds": retry_after,
    }, status=429)
    response["Retry-After"] = str(retry_after)
    return response


def health(request):
    """Operational status without contacting any external store."""
    aggregator = SearchAggregator()
    store_keys = list(aggregator.adapter_classes)
    open_circuits = {}
    now = time.time()
    for key in store_keys:
        state = circuit_state(key)
        if state.get("open_until", 0) > now:
            open_circuits[key] = max(1, int(state["open_until"] - now))

    catalog = mercadia_catalog_health_status()
    path = mercadia_catalog_path()
    try:
        catalog_bytes = path.stat().st_size if path.exists() else 0
    except OSError:
        catalog_bytes = 0

    cache_status = cache_health()
    degraded = (
        not cache_status.get("ok", False)
        or catalog.get("freshness") == "stale"
        or (_mercadia_bridge_enabled() and not catalog.get("ready"))
    )
    payload = {
        "ok": True,
        "degraded": bool(degraded),
        "service": "fetchuccini",
        "version": str(getattr(settings, "FETCHUCCINI_VERSION", "unknown")),
        "uptime_seconds": max(0, int(now - _APP_STARTED_AT)),
        "cache": cache_status,
        "concurrency": {
            "aggregate_store_workers": max(1, int(getattr(settings, "FETCHUCCINI_STORE_CONCURRENCY", 4))),
            "global_store_limit_per_process": store_gate_limit(),
        },
        "mercadia_catalog_ready": bool(catalog.get("ready")),
        "mercadia_catalog_bytes": catalog_bytes,
        "mercadia_catalog_count": int(catalog.get("count") or 0),
        "mercadia_catalog_age_seconds": catalog.get("age_seconds"),
        "mercadia_catalog_freshness": catalog.get("freshness"),
        "open_store_circuits": open_circuits,
        "metrics_available": True,
    }
    if (request.GET.get("details") or "").strip().lower() in {"1", "true", "yes"}:
        payload["metrics"] = metrics_snapshot(store_keys)
    return JsonResponse(payload)


def _disabled_store_keys():
    return set(getattr(settings, "FETCHUCCINI_DISABLED_STORES", ()))


def _is_in_stock_result(row):
    if not row.get("available"):
        return False
    stock = row.get("stock")
    if stock is None:
        return True
    try:
        return int(stock) > 0
    except (TypeError, ValueError):
        return True


def index(request):
    disabled = _disabled_store_keys()
    return render(request, "searchapp/index.html", {
        "disabled_store_keys": disabled,
        "disabled_store_count": len(disabled),
        "enabled_store_count": max(0, 7 - len(disabled)),
    })


def _validate_query(request):
    query = (request.GET.get("q") or "").strip()
    if not query:
        return None, JsonResponse({"error": "Falta el parámetro q."}, status=400)
    if len(query) > 120:
        return None, JsonResponse({"error": "La búsqueda es demasiado larga."}, status=400)
    return query, None


def _selected_store_keys(request, aggregator):
    store_param = (request.GET.get("stores") or "").strip()
    requested = [s.strip() for s in store_param.split(",") if s.strip()]
    if not requested:
        requested = list(aggregator.adapter_classes)
    disabled = _disabled_store_keys()
    return [
        key for key in requested
        if key in aggregator.adapter_classes and key not in disabled
    ]


def _store_cache_keys(query: str, store_key: str):
    # v0.35: accent/punctuation variants share the same snapshot.
    normalized = normalize_card_search_text(query) or query.casefold()
    raw = f"{normalized}|{store_key}".encode("utf-8")
    digest = hashlib.sha256(raw).hexdigest()
    return f"store-search:v19:fresh:{digest}", f"store-search:v19:stale:{digest}"


def _store_refresh_lock_key(query: str, store_key: str) -> str:
    normalized = normalize_card_search_text(query) or query.casefold()
    raw = f"{normalized}|{store_key}".encode("utf-8")
    return f"store-refresh:v1:{hashlib.sha256(raw).hexdigest()}"


def _acquire_store_refresh_lock(query: str, store_key: str) -> tuple[str, bool]:
    token = secrets.token_hex(8)
    try:
        result = cache.add(
            _store_refresh_lock_key(query, store_key),
            token,
            timeout=max(10, int(getattr(settings, "FETCHUCCINI_REFRESH_LOCK_SECONDS", 60))),
        )
        # Some tolerant Redis clients return None when Redis is unreachable.
        # Treat that as fail-open so users do not wait on a lock that was never set.
        acquired = True if result is None else bool(result)
        if (
            not acquired
            and str(getattr(settings, "FETCHUCCINI_CACHE_BACKEND", "file")) == "redis"
            and not cache_health().get("ok", False)
        ):
            acquired = True
    except Exception:
        acquired = True
    return token, acquired


def _release_store_refresh_lock(query: str, store_key: str, token: str) -> None:
    key = _store_refresh_lock_key(query, store_key)
    try:
        # Avoid deleting a newer worker's lock if ours somehow expired first.
        if cache.get(key) == token:
            cache.delete(key)
    except Exception:
        return


def _wait_for_coalesced_snapshot(fresh_key: str, timeout_seconds: float):
    deadline = time.monotonic() + max(0.0, timeout_seconds)
    while time.monotonic() < deadline:
        try:
            snapshot = cache.get(fresh_key)
        except Exception:
            return None
        if snapshot is not None:
            return snapshot
        time.sleep(0.10)
    return None


def _age_seconds(snapshot):
    try:
        return max(0, int(time.time() - float(snapshot.get("cached_at", time.time()))))
    except (TypeError, ValueError):
        return 0


def _response_from_snapshot(snapshot, *, fresh=False, stale=False, error=None):
    results = dedupe_listing_dicts(
        normalize_listing_dict(row)
        for row in snapshot.get("results", [])
        if isinstance(row, dict) and _is_in_stock_result(row)
    )
    store_info = dict(snapshot.get("store", {}))
    store_info["count"] = len(results)
    age = _age_seconds(snapshot)

    data = {
        "query": snapshot["query"],
        "store_key": snapshot["store_key"],
        "results": results,
        "store": store_info,
        "cached": True,
        "fresh": bool(fresh),
        "stale": bool(stale),
        "age_seconds": age,
    }
    if snapshot.get("bridge"):
        data["bridge"] = True
        data["bridge_synced_at"] = snapshot.get("cached_at")
        data["bridge_age_seconds"] = age
    if error:
        data["store"]["error"] = error
    return data



def _mercadia_bridge_enabled():
    return bool(getattr(settings, "MERCADIA_BRIDGE_ENABLED", False))


def _mercadia_bridge_authorized(request):
    expected = (getattr(settings, "MERCADIA_BRIDGE_KEY", "") or "").strip()
    provided = (request.headers.get("X-Fetchuccini-Bridge-Key") or "").strip()
    return bool(expected and provided and secrets.compare_digest(expected, provided))


def _queue_mercadia_bridge_query(query: str, *, due_now=True):
    normalized = normalize_card_search_text(query) or " ".join(query.casefold().split())
    now = float(time.time())
    pending = cache.get(MERCADIA_BRIDGE_PENDING_KEY) or {}
    previous = pending.get(normalized) or {}
    try:
        previous_due = float(previous.get("next_sync_at", now))
    except (TypeError, ValueError):
        previous_due = now

    pending[normalized] = {
        "q": query,
        "requested_at": float(previous.get("requested_at") or now),
        "last_requested_at": now,
        "next_sync_at": min(previous_due, now) if due_now else previous_due,
    }
    cache.set(MERCADIA_BRIDGE_PENDING_KEY, pending, MERCADIA_BRIDGE_PENDING_SECONDS)


def _touch_mercadia_bridge_query(query: str):
    normalized = normalize_card_search_text(query) or " ".join(query.casefold().split())
    now = float(time.time())
    pending = cache.get(MERCADIA_BRIDGE_PENDING_KEY) or {}
    previous = pending.get(normalized)
    if previous is None:
        pending[normalized] = {
            "q": query,
            "requested_at": now,
            "last_requested_at": now,
            "next_sync_at": now + MERCADIA_BRIDGE_SYNC_SECONDS,
        }
    else:
        previous = dict(previous)
        previous["q"] = query
        previous["last_requested_at"] = now
        previous.setdefault("next_sync_at", now + MERCADIA_BRIDGE_SYNC_SECONDS)
        pending[normalized] = previous
    cache.set(MERCADIA_BRIDGE_PENDING_KEY, pending, MERCADIA_BRIDGE_PENDING_SECONDS)


def _schedule_next_mercadia_bridge_sync(query: str):
    normalized = normalize_card_search_text(query) or " ".join(query.casefold().split())
    now = float(time.time())
    pending = cache.get(MERCADIA_BRIDGE_PENDING_KEY) or {}
    previous = pending.get(normalized) or {}
    pending[normalized] = {
        "q": query,
        "requested_at": float(previous.get("requested_at") or now),
        "last_requested_at": float(previous.get("last_requested_at") or now),
        "next_sync_at": now + MERCADIA_BRIDGE_SYNC_SECONDS,
    }
    cache.set(MERCADIA_BRIDGE_PENDING_KEY, pending, MERCADIA_BRIDGE_PENDING_SECONDS)


def _cleanup_and_due_mercadia_jobs(limit: int):
    now = float(time.time())
    pending = cache.get(MERCADIA_BRIDGE_PENDING_KEY) or {}
    kept = {}
    due = []
    for normalized, item in pending.items():
        try:
            last_requested = float(item.get("last_requested_at") or item.get("requested_at") or now)
        except (TypeError, ValueError):
            last_requested = now
        if now - last_requested > MERCADIA_BRIDGE_ACTIVE_SECONDS:
            continue
        kept[normalized] = item
        try:
            next_sync = float(item.get("next_sync_at") or 0)
        except (TypeError, ValueError):
            next_sync = 0
        if next_sync <= now:
            due.append(item)

    cache.set(MERCADIA_BRIDGE_PENDING_KEY, kept, MERCADIA_BRIDGE_PENDING_SECONDS)
    due.sort(key=lambda item: float(item.get("next_sync_at") or item.get("requested_at") or 0))
    return due[:limit], len(kept)


def _mercadia_bridge_waiting_payload(query: str, *, stale_snapshot=None):
    if stale_snapshot is not None:
        return _response_from_snapshot(
            stale_snapshot,
            stale=True,
            error="Mercadia Bridge: esperando la próxima sincronización local.",
        )
    return {
        "query": query,
        "store_key": "mercadia",
        "results": [],
        "store": {
            "store": "Mercadia",
            "count": 0,
            "elapsed_ms": 0,
            "error": "Mercadia Bridge: pendiente de sincronización local.",
        },
        "cached": False,
        "fresh": False,
        "stale": False,
        "age_seconds": 0,
        "bridge": True,
        "bridge_pending": True,
    }


def _mercadia_catalog_payload(query: str):
    rows, status = mercadia_catalog_search(query)
    if not status.get("ready"):
        return None
    age = int(status.get("age_seconds") or 0)
    freshness = status.get("freshness") or "unknown"
    stale = freshness == "stale"
    warning = freshness == "warning"
    return {
        "query": query,
        "store_key": "mercadia",
        "results": rows,
        "store": {
            "store": "Mercadia",
            "count": len(rows),
            "elapsed_ms": 0,
            "error": None,
        },
        "cached": True,
        "fresh": not stale,
        "stale": stale,
        "age_seconds": age,
        "bridge": True,
        "bridge_catalog": True,
        "bridge_synced_at": status.get("synced_at"),
        "bridge_age_seconds": age,
        "catalog_count": status.get("count", 0),
        "catalog_category_count": status.get("category_count", 0),
        "catalog_failed_category_count": status.get("failed_category_count", 0),
        "catalog_freshness": freshness,
        "catalog_warning": warning,
    }


def _bridge_json(request):
    try:
        return json.loads(request.body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return None


@require_GET
def mercadia_catalog_status_api(request):
    if not _mercadia_bridge_authorized(request):
        return JsonResponse({"error": "No autorizado."}, status=403)
    return JsonResponse(mercadia_catalog_status())


@csrf_exempt
@require_POST
def mercadia_catalog_start_api(request):
    if not _mercadia_bridge_authorized(request):
        return JsonResponse({"error": "No autorizado."}, status=403)
    payload = _bridge_json(request)
    if payload is None:
        return JsonResponse({"error": "JSON inválido."}, status=400)
    sync_id = str(payload.get("sync_id") or "").strip()
    if not sync_id:
        return JsonResponse({"error": "Falta sync_id."}, status=400)
    try:
        result = mercadia_catalog_begin_sync(sync_id, metadata=payload.get("metadata") or {})
    except (ValueError, OSError) as exc:
        return JsonResponse({"error": str(exc)}, status=400)
    return JsonResponse(result)


@csrf_exempt
@require_POST
def mercadia_catalog_batch_api(request):
    if not _mercadia_bridge_authorized(request):
        return JsonResponse({"error": "No autorizado."}, status=403)
    payload = _bridge_json(request)
    if payload is None:
        return JsonResponse({"error": "JSON inválido."}, status=400)
    sync_id = str(payload.get("sync_id") or "").strip()
    rows = payload.get("results") or []
    try:
        result = mercadia_catalog_append_batch(sync_id, rows)
    except (ValueError, OSError, FileNotFoundError) as exc:
        return JsonResponse({"error": str(exc)}, status=400)
    return JsonResponse(result)


@csrf_exempt
@require_POST
def mercadia_catalog_finish_api(request):
    if not _mercadia_bridge_authorized(request):
        return JsonResponse({"error": "No autorizado."}, status=403)
    payload = _bridge_json(request)
    if payload is None:
        return JsonResponse({"error": "JSON inválido."}, status=400)
    sync_id = str(payload.get("sync_id") or "").strip()
    try:
        result = mercadia_catalog_finish_sync(sync_id, metadata=payload.get("metadata") or {})
    except ValueError as exc:
        # A suspiciously small full sync is a conflict with the last known-good
        # catalog, not malformed JSON. The previous catalog remains untouched.
        return JsonResponse({"error": str(exc), "catalog_preserved": True}, status=409)
    except (OSError, FileNotFoundError) as exc:
        return JsonResponse({"error": str(exc)}, status=400)
    return JsonResponse(result)


@require_GET
def mercadia_bridge_jobs_api(request):
    if not _mercadia_bridge_authorized(request):
        return JsonResponse({"error": "No autorizado."}, status=403)

    try:
        limit = max(1, min(int(request.GET.get("limit") or 50), 200))
    except ValueError:
        limit = 50

    jobs, tracked_count = _cleanup_and_due_mercadia_jobs(limit)
    return JsonResponse({
        "jobs": jobs,
        "count": len(jobs),
        "tracked_count": tracked_count,
        "sync_interval_seconds": MERCADIA_BRIDGE_SYNC_SECONDS,
    })


@csrf_exempt
@require_POST
def mercadia_bridge_push_api(request):
    if not _mercadia_bridge_authorized(request):
        return JsonResponse({"error": "No autorizado."}, status=403)

    try:
        payload = json.loads(request.body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return JsonResponse({"error": "JSON inválido."}, status=400)

    query = str(payload.get("q") or "").strip()
    if not query or len(query) > 120:
        return JsonResponse({"error": "Consulta inválida."}, status=400)

    raw_results = payload.get("results") or []
    if not isinstance(raw_results, list):
        return JsonResponse({"error": "results debe ser una lista."}, status=400)

    cleaned = []
    for row in raw_results[:500]:
        if not isinstance(row, dict):
            continue
        row = normalize_listing_dict(row)
        row["store"] = "Mercadia"
        if _is_in_stock_result(row):
            cleaned.append(row)
    cleaned = dedupe_listing_dicts(cleaned)

    try:
        elapsed_ms = max(0, int(payload.get("elapsed_ms") or 0))
    except (TypeError, ValueError):
        elapsed_ms = 0

    snapshot = {
        "query": query,
        "store_key": "mercadia",
        "results": cleaned,
        "store": {
            "store": "Mercadia",
            "count": len(cleaned),
            "elapsed_ms": elapsed_ms,
            "error": None,
        },
        "cached_at": time.time(),
        "bridge": True,
    }
    fresh_key, stale_key = _store_cache_keys(query, "mercadia")
    cache.set(fresh_key, snapshot, MERCADIA_BRIDGE_FRESH_SECONDS)
    cache.set(stale_key, snapshot, MERCADIA_BRIDGE_STALE_SECONDS)
    _schedule_next_mercadia_bridge_sync(query)

    return JsonResponse({
        "ok": True,
        "query": query,
        "count": len(cleaned),
        "synced_at": snapshot["cached_at"],
        "next_sync_seconds": MERCADIA_BRIDGE_SYNC_SECONDS,
    })


def autocomplete_api(request):
    """Return Scryfall card-name suggestions for the search box.

    Minimum 2 characters plus a one-hour cache keeps the public Scryfall API
    comfortably below its rate limits even when several users type at once.
    """
    limited = _rate_limit_response(request, "autocomplete")
    if limited:
        return limited
    query = (request.GET.get("q") or "").strip()
    if len(query) < 2:
        return JsonResponse({"query": query, "suggestions": []})
    if len(query) > 80:
        return JsonResponse({"query": query, "suggestions": []})

    normalized = normalize_card_search_text(query) or query.casefold()
    digest = hashlib.sha256(normalized.encode("utf-8")).hexdigest()
    cache_key = f"autocomplete:v17:{digest}"
    cached = cache.get(cache_key)
    if cached is not None:
        return JsonResponse({"query": query, "suggestions": cached, "cached": True})

    suggestions = ScryfallService().autocomplete(query, limit=12)
    cache.set(cache_key, suggestions, AUTOCOMPLETE_CACHE_SECONDS)
    return JsonResponse({"query": query, "suggestions": suggestions, "cached": False})


def search_store_api(request):
    """Fetch one store progressively with cache, coalescing and stale fallback."""
    limited = _rate_limit_response(request, "search_store")
    if limited:
        return limited
    query, error_response = _validate_query(request)
    if error_response:
        return error_response

    store_key = (request.GET.get("store") or "").strip()
    aggregator = SearchAggregator()
    if store_key not in aggregator.adapter_classes:
        return JsonResponse({"error": "Tienda inválida."}, status=400)

    if store_key in _disabled_store_keys():
        adapter_name = aggregator.adapter_classes[store_key].name
        return JsonResponse({
            "query": query,
            "store_key": store_key,
            "results": [],
            "store": {
                "store": adapter_name,
                "count": 0,
                "elapsed_ms": 0,
                "error": None,
            },
            "cached": False,
            "fresh": False,
            "stale": False,
            "age_seconds": 0,
            "unavailable": True,
            "message": "Temporalmente no disponible en la versión online.",
        })

    # Mercadia normally answers from the persistent catalog and does not need
    # an outbound request from Railway.
    if store_key == "mercadia" and _mercadia_bridge_enabled():
        catalog_payload = _mercadia_catalog_payload(query)
        if catalog_payload is not None:
            record_store_result(
                store_key,
                elapsed_ms=0,
                success=True,
                source="catalog",
                count=len(catalog_payload.get("results") or []),
            )
            return JsonResponse(catalog_payload)

    fresh_key, stale_key = _store_cache_keys(query, store_key)
    fresh = cache.get(fresh_key)
    if fresh is not None:
        if store_key == "mercadia" and _mercadia_bridge_enabled() and fresh.get("bridge"):
            _touch_mercadia_bridge_query(query)
        payload = _response_from_snapshot(fresh, fresh=True)
        record_store_result(store_key, elapsed_ms=0, success=True, source="cache", count=len(payload.get("results") or []))
        return JsonResponse(payload)

    # Mercadia legacy bridge mode: queue instead of hammering an origin that
    # rejects hosted IPs.
    if store_key == "mercadia" and _mercadia_bridge_enabled():
        _queue_mercadia_bridge_query(query)
        stale = cache.get(stale_key)
        payload = _mercadia_bridge_waiting_payload(query, stale_snapshot=stale)
        record_store_result(
            store_key,
            elapsed_ms=0,
            success=bool(stale),
            source="stale" if stale else "cache",
            count=len(payload.get("results") or []),
        )
        return JsonResponse(payload)

    # v0.36 single-flight: when several users miss the same cache entry at the
    # same time, one request refreshes the origin while peers briefly wait for
    # its snapshot. Redis makes this work across Gunicorn workers/replicas too.
    stale_before_refresh = cache.get(stale_key)
    lock_token, lock_acquired = _acquire_store_refresh_lock(query, store_key)
    if not lock_acquired:
        coalesced = _wait_for_coalesced_snapshot(
            fresh_key,
            float(getattr(settings, "FETCHUCCINI_REFRESH_WAIT_SECONDS", 2.5)),
        )
        if coalesced is not None:
            payload = _response_from_snapshot(coalesced, fresh=True)
            payload["coalesced"] = True
            record_store_result(store_key, elapsed_ms=0, success=True, source="coalesced", count=len(payload.get("results") or []))
            return JsonResponse(payload)
        if stale_before_refresh is not None:
            payload = _response_from_snapshot(stale_before_refresh, stale=True)
            payload["refreshing"] = True
            payload["coalesced"] = True
            record_store_result(store_key, elapsed_ms=0, success=True, source="coalesced", count=len(payload.get("results") or []))
            return JsonResponse(payload)

    try:
        rows, run = aggregator.search_store(query, store_key)
        if run.error:
            stale = stale_before_refresh or cache.get(stale_key)
            if stale is not None:
                payload = _response_from_snapshot(stale, stale=True, error=run.error)
                record_store_result(
                    store_key,
                    elapsed_ms=0,
                    success=True,
                    source="stale",
                    count=len(payload.get("results") or []),
                    count_request=False,
                )
                return JsonResponse(payload)
            return JsonResponse({
                "query": query,
                "store_key": store_key,
                "results": [],
                "store": {
                    "store": run.store,
                    "count": 0,
                    "elapsed_ms": run.elapsed_ms,
                    "error": run.error,
                },
                "cached": False,
                "fresh": False,
                "stale": False,
                "age_seconds": 0,
            })

        snapshot = {
            "query": query,
            "store_key": store_key,
            "results": [row.to_dict() for row in rows],
            "store": {
                "store": run.store,
                "count": run.count,
                "elapsed_ms": run.elapsed_ms,
                "error": None,
            },
            "cached_at": time.time(),
        }
        fresh_seconds = MAGICDEALERS_FRESH_CACHE_SECONDS if store_key == "magicdealers" else FRESH_CACHE_SECONDS
        cache.set(fresh_key, snapshot, fresh_seconds)
        cache.set(stale_key, snapshot, STALE_CACHE_SECONDS)

        return JsonResponse({
            **snapshot,
            "cached": False,
            "fresh": True,
            "stale": False,
            "age_seconds": 0,
        })
    finally:
        if lock_acquired:
            _release_store_refresh_lock(query, store_key, lock_token)


def search_cache_api(request):
    """Return existing cache only; never contacts an external store."""
    limited = _rate_limit_response(request, "search_cache")
    if limited:
        return limited
    query, error_response = _validate_query(request)
    if error_response:
        return error_response

    aggregator = SearchAggregator()
    selected = _selected_store_keys(request, aggregator)
    snapshots = []

    for store_key in selected:
        if store_key == "mercadia" and _mercadia_bridge_enabled():
            catalog_payload = _mercadia_catalog_payload(query)
            if catalog_payload is not None:
                snapshots.append(catalog_payload)
                record_store_result(
                    store_key, elapsed_ms=0, success=True, source="catalog",
                    count=len(catalog_payload.get("results") or []), count_request=False,
                )
                continue

        fresh_key, stale_key = _store_cache_keys(query, store_key)
        fresh = cache.get(fresh_key)
        if fresh is not None:
            if store_key == "mercadia" and _mercadia_bridge_enabled() and fresh.get("bridge"):
                _touch_mercadia_bridge_query(query)
            payload = _response_from_snapshot(fresh, fresh=True)
            snapshots.append(payload)
            record_store_result(
                store_key, elapsed_ms=0, success=True, source="cache",
                count=len(payload.get("results") or []), count_request=False,
            )
            continue

        stale = cache.get(stale_key)
        if stale is not None:
            if store_key == "mercadia" and _mercadia_bridge_enabled() and stale.get("bridge"):
                _queue_mercadia_bridge_query(query, due_now=True)
            payload = _response_from_snapshot(stale, stale=True)
            snapshots.append(payload)
            record_store_result(
                store_key, elapsed_ms=0, success=True, source="stale",
                count=len(payload.get("results") or []), count_request=False,
            )

    return JsonResponse({"query": query, "stores": snapshots})


def search_api(request):
    """Compatibility endpoint: waits for all stores like the original MVP."""
    limited = _rate_limit_response(request, "search_all")
    if limited:
        return limited
    query, error_response = _validate_query(request)
    if error_response:
        return error_response

    aggregator = SearchAggregator()
    stores = _selected_store_keys(request, aggregator)
    catalog_payload = None
    live_stores = list(stores)
    if "mercadia" in live_stores and _mercadia_bridge_enabled():
        catalog_payload = _mercadia_catalog_payload(query)
        if catalog_payload is not None:
            live_stores.remove("mercadia")

    listings, runs = aggregator.search(query, live_stores)
    results = [row.to_dict() for row in listings]
    store_payloads = [
        {"store": r.store, "count": r.count, "elapsed_ms": r.elapsed_ms, "error": r.error}
        for r in runs
    ]
    if catalog_payload is not None:
        results.extend(catalog_payload.get("results") or [])
        store_payloads.append(catalog_payload.get("store") or {"store": "Mercadia", "count": 0, "elapsed_ms": 0, "error": None})

    results = dedupe_listing_dicts(results)
    payload = {
        "query": query,
        "count": len(results),
        "results": results,
        "stores": sorted(store_payloads, key=lambda row: str(row.get("store") or "")),
    }
    return JsonResponse(payload)
