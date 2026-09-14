from __future__ import annotations

import json
from bisect import bisect_left
import os
import re
import threading
import time
from pathlib import Path

from django.conf import settings

from .listing_normalization import (
    dedupe_listing_dicts,
    normalize_listing_dict,
)
from .utils import normalize_card_search_text


_LOCK = threading.RLock()
_CACHE_MTIME: float | None = None
_CACHE_DATA: dict | None = None
_CACHE_INDEX: dict[str, list[dict]] = {}
_CACHE_NAMES: list[str] = []

_RESERVED_METADATA_KEYS = {"version", "synced_at", "count", "results", "sync_id", "started_at"}


def _safe_metadata(metadata: dict | None) -> dict:
    if not isinstance(metadata, dict):
        return {}
    return {str(key): value for key, value in metadata.items() if str(key) not in _RESERVED_METADATA_KEYS}


def _catalog_dir() -> Path:
    path = Path(getattr(settings, "MERCADIA_CATALOG_DIR"))
    path.mkdir(parents=True, exist_ok=True)
    return path


def catalog_path() -> Path:
    return _catalog_dir() / "mercadia_catalog.json"


def _status_path() -> Path:
    return _catalog_dir() / "mercadia_catalog.status.json"


def _status_payload(data: dict, path: Path) -> dict:
    synced_at = float(data.get("synced_at") or 0)
    age = max(0, int(time.time() - synced_at)) if synced_at else None
    count = int(data.get("count") or len(data.get("results") or []))
    return {
        "ready": True,
        "count": count,
        "synced_at": synced_at or None,
        "age_seconds": age,
        "freshness": _freshness(age),
        "category_count": int(data.get("category_count") or 0),
        "failed_category_count": int(data.get("failed_category_count") or 0),
        "path": str(path),
        "persistent_hint": str(path).startswith("/data/"),
    }


def _write_status_sidecar(data: dict) -> None:
    path = catalog_path()
    payload = _status_payload(data, path)
    small = {
        key: payload[key]
        for key in ("count", "synced_at", "category_count", "failed_category_count")
    }
    status_path = _status_path()
    tmp = status_path.with_suffix(".tmp")
    try:
        tmp.write_text(json.dumps(small, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
        os.replace(tmp, status_path)
    except OSError:
        try:
            tmp.unlink()
        except OSError:
            pass


def _staging_path(sync_id: str) -> Path:
    safe = "".join(ch for ch in sync_id if ch.isalnum() or ch in {"-", "_"})[:80]
    if not safe:
        raise ValueError("sync_id inválido")
    return _catalog_dir() / f"mercadia_catalog.{safe}.jsonl"


def _staging_meta_path(sync_id: str) -> Path:
    return _staging_path(sync_id).with_suffix(".meta.json")


def _normalize(value: str | None) -> str:
    return normalize_card_search_text(value)


def _is_in_stock(row: dict) -> bool:
    if not row.get("available"):
        return False
    stock = row.get("stock")
    if stock is None:
        return True
    try:
        return int(stock) > 0
    except (TypeError, ValueError):
        return True


def _freshness(age_seconds: int | None) -> str:
    if age_seconds is None:
        return "unknown"
    warn_after = max(60, int(getattr(settings, "MERCADIA_CATALOG_WARN_AGE_SECONDS", 12 * 60 * 60)))
    stale_after = max(warn_after, int(getattr(settings, "MERCADIA_CATALOG_STALE_AGE_SECONDS", 36 * 60 * 60)))
    if age_seconds >= stale_after:
        return "stale"
    if age_seconds >= warn_after:
        return "warning"
    return "fresh"


def _cleanup_staging_files(*, now: float | None = None) -> int:
    """Delete abandoned bridge staging files so the persistent Volume stays tidy."""
    current = float(now if now is not None else time.time())
    max_age = max(60 * 60, int(getattr(settings, "MERCADIA_STAGING_MAX_AGE_SECONDS", 24 * 60 * 60)))
    removed = 0
    directory = _catalog_dir()
    for path in directory.glob("mercadia_catalog.*"):
        if path.name == "mercadia_catalog.json" or path.suffix == ".tmp":
            continue
        if not (path.name.endswith(".jsonl") or path.name.endswith(".meta.json")):
            continue
        try:
            if current - path.stat().st_mtime <= max_age:
                continue
            path.unlink()
            removed += 1
        except OSError:
            continue
    return removed


def _rebuild_index(data: dict | None) -> None:
    """Build an in-memory card-name index for exact/prefix catalog lookups."""
    global _CACHE_INDEX, _CACHE_NAMES
    index: dict[str, list[dict]] = {}
    if data:
        for raw in data.get("results") or []:
            if not isinstance(raw, dict) or not _is_in_stock(raw):
                continue
            name = _normalize(raw.get("card_name"))
            if not name:
                continue
            index.setdefault(name, []).append(raw)
    _CACHE_INDEX = index
    _CACHE_NAMES = sorted(index)


def _load_from_disk() -> dict | None:
    global _CACHE_DATA, _CACHE_MTIME
    path = catalog_path()
    if not path.exists():
        _CACHE_DATA = None
        _CACHE_MTIME = None
        return None

    stat = path.stat()
    if _CACHE_DATA is not None and _CACHE_MTIME == stat.st_mtime:
        if not _CACHE_INDEX and (_CACHE_DATA.get("results") or []):
            _rebuild_index(_CACHE_DATA)
        return _CACHE_DATA

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None

    if not isinstance(data, dict) or not isinstance(data.get("results"), list):
        return None

    _CACHE_DATA = data
    _CACHE_MTIME = stat.st_mtime
    _rebuild_index(data)
    return data


def catalog_status() -> dict:
    with _LOCK:
        data = _load_from_disk()
        path = catalog_path()
        if not data:
            return {
                "ready": False,
                "count": 0,
                "synced_at": None,
                "age_seconds": None,
                "freshness": "missing",
                "path": str(path),
                "persistent_hint": str(path).startswith("/data/"),
            }
        return _status_payload(data, path)


def catalog_status_lightweight() -> dict:
    """Health-check status without parsing the ~30MB catalog on cold start."""
    with _LOCK:
        path = catalog_path()
        if not path.exists():
            return {
                "ready": False,
                "count": 0,
                "synced_at": None,
                "age_seconds": None,
                "freshness": "missing",
                "path": str(path),
                "persistent_hint": str(path).startswith("/data/"),
            }

        # If this worker already loaded the catalog, this is exact and free.
        try:
            stat = path.stat()
        except OSError:
            stat = None
        if _CACHE_DATA is not None and stat is not None and _CACHE_MTIME == stat.st_mtime:
            return _status_payload(_CACHE_DATA, path)

        status_path = _status_path()
        try:
            raw = json.loads(status_path.read_text(encoding="utf-8"))
            if isinstance(raw, dict):
                return _status_payload(raw, path)
        except (OSError, json.JSONDecodeError, TypeError, ValueError):
            pass

        # Compatibility with catalogs created before v0.36: metadata sits at
        # the beginning of the compact JSON, so read only a small prefix.
        count = 0
        synced_at = 0.0
        try:
            with path.open("r", encoding="utf-8") as handle:
                prefix = handle.read(4096)
            count_match = re.search(r'"count"\s*:\s*(\d+)', prefix)
            synced_match = re.search(r'"synced_at"\s*:\s*([0-9.]+)', prefix)
            if count_match:
                count = int(count_match.group(1))
            if synced_match:
                synced_at = float(synced_match.group(1))
        except (OSError, ValueError):
            pass

        if not synced_at and stat is not None:
            synced_at = float(stat.st_mtime)
        return _status_payload({"count": count, "synced_at": synced_at}, path)


def search_catalog(query: str, limit: int = 1500) -> tuple[list[dict], dict]:
    with _LOCK:
        data = _load_from_disk()
        if not data:
            return [], catalog_status()

        needle = _normalize(query)
        if not needle:
            return [], catalog_status()

        results: list[dict] = []

        # O(1) exact lookup, then binary-search only matching normalized names.
        for row in _CACHE_INDEX.get(needle, []):
            results.append(normalize_listing_dict(row))
            if len(results) >= limit:
                return dedupe_listing_dicts(results), catalog_status()

        start = bisect_left(_CACHE_NAMES, needle)
        end = bisect_left(_CACHE_NAMES, needle + "\uffff")
        for name in _CACHE_NAMES[start:end]:
            if name == needle:
                continue
            for row in _CACHE_INDEX.get(name, []):
                results.append(normalize_listing_dict(row))
                if len(results) >= limit:
                    return dedupe_listing_dicts(results), catalog_status()

        return dedupe_listing_dicts(results), catalog_status()


def begin_sync(sync_id: str, *, metadata: dict | None = None) -> dict:
    with _LOCK:
        cleaned = _cleanup_staging_files()
        path = _staging_path(sync_id)
        meta_path = _staging_meta_path(sync_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("", encoding="utf-8")
        meta = {
            "sync_id": sync_id,
            "started_at": time.time(),
            **_safe_metadata(metadata),
        }
        meta_path.write_text(json.dumps(meta, ensure_ascii=False), encoding="utf-8")
        return {"ok": True, "sync_id": sync_id, "stale_staging_removed": cleaned}


def append_batch(sync_id: str, rows: list[dict]) -> dict:
    if not isinstance(rows, list):
        raise ValueError("rows debe ser una lista")
    if len(rows) > 600:
        raise ValueError("batch demasiado grande")

    cleaned = []
    for raw in rows:
        if not isinstance(raw, dict):
            continue
        row = normalize_listing_dict(raw)
        row["store"] = "Mercadia"
        if _is_in_stock(row):
            cleaned.append(row)

    with _LOCK:
        path = _staging_path(sync_id)
        if not path.exists():
            raise FileNotFoundError("sync no iniciado")
        with path.open("a", encoding="utf-8") as handle:
            for row in cleaned:
                handle.write(json.dumps(row, ensure_ascii=False, separators=(",", ":")))
                handle.write("\n")
    return {"ok": True, "accepted": len(cleaned)}


def _validate_publish_size(new_count: int, current_count: int) -> None:
    """Reject suspiciously incomplete syncs without replacing a healthy catalog."""
    min_count = max(0, int(getattr(settings, "MERCADIA_CATALOG_MIN_PUBLISH_COUNT", 15000)))
    try:
        min_ratio = float(getattr(settings, "MERCADIA_CATALOG_MIN_PUBLISH_RATIO", 0.65))
    except (TypeError, ValueError):
        min_ratio = 0.65
    min_ratio = min(1.0, max(0.0, min_ratio))

    ratio = new_count / current_count if current_count else 1.0
    too_small_absolute = min_count > 0 and new_count < min_count
    too_small_relative = current_count > 0 and ratio < min_ratio
    if too_small_absolute or too_small_relative:
        previous_text = str(current_count) if current_count else "sin catálogo previo"
        raise ValueError(
            "Catálogo Mercadia rechazado por seguridad: "
            f"nuevo={new_count}, anterior={previous_text}, ratio={ratio:.2f}. "
            "Se conserva el catálogo anterior si existe."
        )


def _discard_staging(sync_id: str) -> None:
    for path in (_staging_path(sync_id), _staging_meta_path(sync_id)):
        try:
            path.unlink()
        except OSError:
            pass


def finish_sync(sync_id: str, *, metadata: dict | None = None) -> dict:
    global _CACHE_DATA, _CACHE_MTIME
    with _LOCK:
        staging = _staging_path(sync_id)
        if not staging.exists():
            raise FileNotFoundError("sync no iniciado")

        rows: list[dict] = []
        with staging.open("r", encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if not line:
                    continue
                try:
                    row = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if not isinstance(row, dict):
                    continue
                row = normalize_listing_dict(row)
                row["store"] = "Mercadia"
                if _is_in_stock(row):
                    rows.append(row)

        rows = dedupe_listing_dicts(rows)
        rows.sort(
            key=lambda r: (
                _normalize(r.get("card_name")),
                _normalize(r.get("set_name")),
                _normalize(r.get("collector_number")),
                _normalize(r.get("condition")),
                str(r.get("price") or ""),
            )
        )

        current = _load_from_disk()
        current_count = len(current.get("results") or []) if current else 0
        try:
            _validate_publish_size(len(rows), current_count)
        except ValueError:
            _discard_staging(sync_id)
            raise

        now = time.time()
        payload = {
            "version": 2,
            "synced_at": now,
            "count": len(rows),
            "results": rows,
            **_safe_metadata(metadata),
        }

        final_path = catalog_path()
        tmp_path = final_path.with_suffix(".tmp")
        tmp_path.write_text(json.dumps(payload, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
        os.replace(tmp_path, final_path)
        _write_status_sidecar(payload)
        _discard_staging(sync_id)

        _CACHE_DATA = payload
        _CACHE_MTIME = final_path.stat().st_mtime
        _rebuild_index(payload)
        return {
            "ok": True,
            "sync_id": sync_id,
            "count": len(rows),
            "previous_count": current_count,
            "synced_at": now,
            "freshness": "fresh",
            "path": str(final_path),
        }
