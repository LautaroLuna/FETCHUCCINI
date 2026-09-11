from __future__ import annotations

import os
import sys
import time
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from searchapp.services.stores.mercadia import MercadiaAdapter


def _env(name: str) -> str:
    return (os.environ.get(name) or "").strip()


def _in_stock(row: dict) -> bool:
    if not row.get("available"):
        return False
    stock = row.get("stock")
    if stock is None:
        return True
    try:
        return int(stock) > 0
    except (TypeError, ValueError):
        return True


def main() -> int:
    base_url = _env("FETCHUCCINI_URL").rstrip("/")
    bridge_key = _env("MERCADIA_BRIDGE_KEY")
    if not base_url or not bridge_key:
        print("[ERROR] Faltan FETCHUCCINI_URL o MERCADIA_BRIDGE_KEY. Ejecutá mercadia_bridge_setup.bat.")
        return 2

    headers = {
        "X-Fetchuccini-Bridge-Key": bridge_key,
        "Accept": "application/json",
        "User-Agent": "Fetchuccini-Mercadia-Bridge/1.0",
    }

    print(f"[INFO] Consultando trabajos pendientes en {base_url} ...")
    response = requests.get(
        f"{base_url}/api/bridge/mercadia/jobs/",
        params={"limit": 100},
        headers=headers,
        timeout=30,
    )
    if response.status_code == 403:
        print("[ERROR] Railway rechazó la clave del bridge. Revisá MERCADIA_BRIDGE_KEY en Railway y en mercadia_bridge_config.bat.")
        return 3
    response.raise_for_status()
    jobs = response.json().get("jobs") or []

    if not jobs:
        print("[OK] No hay búsquedas de Mercadia pendientes.")
        return 0

    print(f"[INFO] {len(jobs)} búsqueda(s) pendiente(s).")
    adapter = MercadiaAdapter()
    failures = 0

    for index, job in enumerate(jobs, start=1):
        query = str(job.get("q") or "").strip()
        if not query:
            continue
        print(f"[{index}/{len(jobs)}] Mercadia: {query}")
        started = time.perf_counter()
        try:
            # From the home connection we can use Mercadia's full catalog
            # search + product details, so the bridge is not limited to the
            # five suggestions returned by the autocomplete endpoint.
            try:
                listings = adapter._legacy_html_search(query)
            except Exception:
                listings = adapter.search(query)
            results = [row.to_dict() for row in listings]
            results = [row for row in results if _in_stock(row)]
            elapsed_ms = int((time.perf_counter() - started) * 1000)

            pushed = requests.post(
                f"{base_url}/api/bridge/mercadia/push/",
                json={"q": query, "results": results, "elapsed_ms": elapsed_ms},
                headers={**headers, "Content-Type": "application/json"},
                timeout=30,
            )
            pushed.raise_for_status()
            print(f"    [OK] {len(results)} publicación(es) sincronizada(s) en {elapsed_ms} ms.")
        except Exception as exc:
            failures += 1
            print(f"    [ERROR] {type(exc).__name__}: {exc}")

    if failures:
        print(f"[WARN] Terminó con {failures} error(es). El próximo ciclo volverá a intentar los trabajos pendientes.")
        return 1

    print("[OK] Sincronización de Mercadia terminada.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
