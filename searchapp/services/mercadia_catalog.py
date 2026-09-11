from __future__ import annotations

import json
import os
import threading
import time
import unicodedata
from pathlib import Path

from django.conf import settings


_LOCK = threading.RLock()
_CACHE_MTIME: float | None = None
_CACHE_DATA: dict | None = None


def _catalog_dir() -> Path:
    path = Path(getattr(settings, "MERCADIA_CATALOG_DIR"))
    path.mkdir(parents=True, exist_ok=True)
    return path


def catalog_path() -> Path:
    return _catalog_dir() / "mercadia_catalog.json"


def _staging_path(sync_id: str) -> Path:
    safe = "".join(ch for ch in sync_id if ch.isalnum() or ch in {"-", "_"})[:80]
    if not safe:
        raise ValueError("sync_id inválido")
    return _catalog_dir() / f"mercadia_catalog.{safe}.jsonl"


def _staging_meta_path(sync_id: str) -> Path:
    return _staging_path(sync_id).with_suffix(".meta.json")


def _normalize(value: str | None) -> str:
    text = unicodedata.normalize("NFKD", str(value or "")).casefold()
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    return " ".join(text.split())


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


def _dedupe_key(row: dict) -> str:
    for key in ("product_id", "sku", "url"):
        value = row.get(key)
        if value not in (None, ""):
            return f"{key}:{value}"
    return "|".join(
        [
            _normalize(row.get("card_name")),
            _normalize(row.get("set_name")),
            _normalize(row.get("collector_number")),
            _normalize(row.get("language")),
            _normalize(row.get("condition")),
            _normalize(row.get("finish")),
        ]
    )


def _load_from_disk() -> dict | None:
    global _CACHE_DATA, _CACHE_MTIME
    path = catalog_path()
    if not path.exists():
        _CACHE_DATA = None
        _CACHE_MTIME = None
        return None

    stat = path.stat()
    if _CACHE_DATA is not None and _CACHE_MTIME == stat.st_mtime:
        return _CACHE_DATA

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None

    if not isinstance(data, dict) or not isinstance(data.get("results"), list):
        return None

    _CACHE_DATA = data
    _CACHE_MTIME = stat.st_mtime
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
                "path": str(path),
                "persistent_hint": str(path).startswith("/data/"),
            }
        synced_at = float(data.get("synced_at") or 0)
        age = max(0, int(time.time() - synced_at)) if synced_at else None
        return {
            "ready": True,
            "count": len(data.get("results") or []),
            "synced_at": synced_at or None,
            "age_seconds": age,
            "category_count": int(data.get("category_count") or 0),
            "failed_category_count": int(data.get("failed_category_count") or 0),
            "path": str(path),
            "persistent_hint": str(path).startswith("/data/"),
        }


def search_catalog(query: str, limit: int = 1500) -> tuple[list[dict], dict]:
    with _LOCK:
        data = _load_from_disk()
        if not data:
            return [], catalog_status()

        needle = _normalize(query)
        if not needle:
            return [], catalog_status()

        results = []
        exact = []
        prefix = []
        for raw in data.get("results") or []:
            if not isinstance(raw, dict) or not _is_in_stock(raw):
                continue
            name = _normalize(raw.get("card_name"))
            if name == needle:
                exact.append(raw)
            elif name.startswith(needle):
                prefix.append(raw)

        # Exact name first, then prefix matches. This keeps a full-card search
        # focused while still supporting queries such as "lightning".
        for row in exact + prefix:
            results.append(dict(row))
            if len(results) >= limit:
                break

        return results, catalog_status()


def begin_sync(sync_id: str, *, metadata: dict | None = None) -> dict:
    with _LOCK:
        path = _staging_path(sync_id)
        meta_path = _staging_meta_path(sync_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("", encoding="utf-8")
        meta = {
            "sync_id": sync_id,
            "started_at": time.time(),
            **(metadata or {}),
        }
        meta_path.write_text(json.dumps(meta, ensure_ascii=False), encoding="utf-8")
        return {"ok": True, "sync_id": sync_id}


def append_batch(sync_id: str, rows: list[dict]) -> dict:
    if not isinstance(rows, list):
        raise ValueError("rows debe ser una lista")
    if len(rows) > 600:
        raise ValueError("batch demasiado grande")

    cleaned = []
    for raw in rows:
        if not isinstance(raw, dict):
            continue
        row = dict(raw)
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


def finish_sync(sync_id: str, *, metadata: dict | None = None) -> dict:
    global _CACHE_DATA, _CACHE_MTIME
    with _LOCK:
        staging = _staging_path(sync_id)
        if not staging.exists():
            raise FileNotFoundError("sync no iniciado")

        unique: dict[str, dict] = {}
        with staging.open("r", encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if not line:
                    continue
                try:
                    row = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if not isinstance(row, dict) or not _is_in_stock(row):
                    continue
                row["store"] = "Mercadia"
                unique[_dedupe_key(row)] = row

        rows = list(unique.values())
        rows.sort(
            key=lambda r: (
                _normalize(r.get("card_name")),
                _normalize(r.get("set_name")),
                _normalize(r.get("collector_number")),
                _normalize(r.get("condition")),
                str(r.get("price") or ""),
            )
        )
        now = time.time()
        payload = {
            "version": 1,
            "synced_at": now,
            "count": len(rows),
            "results": rows,
            **(metadata or {}),
        }

        final_path = catalog_path()
        tmp_path = final_path.with_suffix(".tmp")
        tmp_path.write_text(json.dumps(payload, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
        os.replace(tmp_path, final_path)

        try:
            staging.unlink()
        except OSError:
            pass
        try:
            _staging_meta_path(sync_id).unlink()
        except OSError:
            pass

        _CACHE_DATA = payload
        _CACHE_MTIME = final_path.stat().st_mtime
        return {
            "ok": True,
            "sync_id": sync_id,
            "count": len(rows),
            "synced_at": now,
            "path": str(final_path),
        }
