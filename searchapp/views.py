import hashlib
import time

from django.conf import settings
from django.core.cache import cache
from django.http import JsonResponse
from django.shortcuts import render

from .services.aggregator import SearchAggregator
from .services.scryfall import ScryfallService


FRESH_CACHE_SECONDS = 5 * 60
STALE_CACHE_SECONDS = 24 * 60 * 60
AUTOCOMPLETE_CACHE_SECONDS = 60 * 60




def health(request):
    """Lightweight health check for the hosting platform."""
    return JsonResponse({"ok": True, "service": "fetchuccini"})


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
    raw = f"{query.casefold()}|{store_key}".encode("utf-8")
    digest = hashlib.sha256(raw).hexdigest()
    return f"store-search:v15:fresh:{digest}", f"store-search:v15:stale:{digest}"


def _age_seconds(snapshot):
    try:
        return max(0, int(time.time() - float(snapshot.get("cached_at", time.time()))))
    except (TypeError, ValueError):
        return 0


def _response_from_snapshot(snapshot, *, fresh=False, stale=False, error=None):
    results = [
        row for row in snapshot.get("results", [])
        if _is_in_stock_result(row)
    ]
    store_info = dict(snapshot.get("store", {}))
    store_info["count"] = len(results)

    data = {
        "query": snapshot["query"],
        "store_key": snapshot["store_key"],
        "results": results,
        "store": store_info,
        "cached": True,
        "fresh": bool(fresh),
        "stale": bool(stale),
        "age_seconds": _age_seconds(snapshot),
    }
    if error:
        data["store"]["error"] = error
    return data


def autocomplete_api(request):
    """Return Scryfall card-name suggestions for the search box.

    Minimum 2 characters plus a one-hour cache keeps the public Scryfall API
    comfortably below its rate limits even when several users type at once.
    """
    query = (request.GET.get("q") or "").strip()
    if len(query) < 2:
        return JsonResponse({"query": query, "suggestions": []})
    if len(query) > 80:
        return JsonResponse({"query": query, "suggestions": []})

    normalized = query.casefold()
    digest = hashlib.sha256(normalized.encode("utf-8")).hexdigest()
    cache_key = f"autocomplete:v16:{digest}"
    cached = cache.get(cache_key)
    if cached is not None:
        return JsonResponse({"query": query, "suggestions": cached, "cached": True})

    suggestions = ScryfallService().autocomplete(query, limit=12)
    cache.set(cache_key, suggestions, AUTOCOMPLETE_CACHE_SECONDS)
    return JsonResponse({"query": query, "suggestions": suggestions, "cached": False})


def search_store_api(request):
    """Fetch one store so results can stream progressively in the browser.

    Fresh cache is returned instantly. If a live refresh fails, the last
    successful snapshot (up to 24h old) is returned as a stale fallback.
    """
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

    fresh_key, stale_key = _store_cache_keys(query, store_key)
    fresh = cache.get(fresh_key)
    if fresh is not None:
        return JsonResponse(_response_from_snapshot(fresh, fresh=True))

    rows, run = aggregator.search_store(query, store_key)
    if run.error:
        stale = cache.get(stale_key)
        if stale is not None:
            return JsonResponse(_response_from_snapshot(
                stale,
                stale=True,
                error=run.error,
            ))
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
    cache.set(fresh_key, snapshot, FRESH_CACHE_SECONDS)
    cache.set(stale_key, snapshot, STALE_CACHE_SECONDS)

    return JsonResponse({
        **snapshot,
        "cached": False,
        "fresh": True,
        "stale": False,
        "age_seconds": 0,
    })


def search_cache_api(request):
    """Return existing cache only; never contacts an external store."""
    query, error_response = _validate_query(request)
    if error_response:
        return error_response

    aggregator = SearchAggregator()
    selected = _selected_store_keys(request, aggregator)
    snapshots = []

    for store_key in selected:
        fresh_key, stale_key = _store_cache_keys(query, store_key)
        fresh = cache.get(fresh_key)
        if fresh is not None:
            snapshots.append(_response_from_snapshot(fresh, fresh=True))
            continue

        stale = cache.get(stale_key)
        if stale is not None:
            snapshots.append(_response_from_snapshot(stale, stale=True))

    return JsonResponse({"query": query, "stores": snapshots})


def search_api(request):
    """Compatibility endpoint: waits for all stores like the original MVP."""
    query, error_response = _validate_query(request)
    if error_response:
        return error_response

    aggregator = SearchAggregator()
    stores = _selected_store_keys(request, aggregator)
    listings, runs = aggregator.search(query, stores)
    payload = {
        "query": query,
        "count": len(listings),
        "results": [row.to_dict() for row in listings],
        "stores": [
            {"store": r.store, "count": r.count, "elapsed_ms": r.elapsed_ms, "error": r.error}
            for r in runs
        ],
    }
    return JsonResponse(payload)
