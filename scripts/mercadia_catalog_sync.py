from __future__ import annotations

import json
import os
import re
import sys
import time
import uuid
from pathlib import Path
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from searchapp.services.stores.mercadia import MercadiaAdapter
from searchapp.services.utils import normalize_space


STATE_PATH = Path(os.environ.get("MERCADIA_CATALOG_LOCAL_STATE") or (ROOT / "mercadia_catalog_local.json"))
LOCK_PATH = STATE_PATH.with_suffix(".lock")
SEED_QUERY = os.environ.get("MERCADIA_CATALOG_SEED_QUERY", "Lightning Bolt")
PAGE_LIMIT = 36
MAX_PAGES_PER_CATEGORY = 60
BATCH_SIZE = 400
REQUEST_DELAY = max(0.0, float(os.environ.get("MERCADIA_CATALOG_DELAY", "0.12")))
PROGRESS_BAR_WIDTH = 24


def _format_duration(seconds: float | int | None) -> str:
    if seconds is None:
        return "--:--"
    seconds = max(0, int(seconds))
    hours, remainder = divmod(seconds, 3600)
    minutes, secs = divmod(remainder, 60)
    if hours:
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"
    return f"{minutes:02d}:{secs:02d}"


def _progress_bar(completed: int, total: int, width: int = PROGRESS_BAR_WIDTH) -> str:
    if total <= 0:
        return "[" + "-" * width + "]"
    ratio = min(1.0, max(0.0, completed / total))
    filled = int(round(ratio * width))
    return "[" + "#" * filled + "-" * (width - filled) + "]"


def _print_progress(label: str, completed: int, total: int, started_at: float, detail: str = "") -> None:
    elapsed = max(0.0, time.time() - started_at)
    percent = (completed / total * 100.0) if total else 0.0
    eta = None
    if completed > 0 and total > completed:
        eta = (elapsed / completed) * (total - completed)
    suffix = f" | {detail}" if detail else ""
    print(
        f"[PROGRESO {label}] {_progress_bar(completed, total)} "
        f"{percent:5.1f}% ({completed}/{total}) "
        f"| transcurrido {_format_duration(elapsed)} "
        f"| ETA {_format_duration(eta)}{suffix}",
        flush=True,
    )


def _env(name: str) -> str:
    return (os.environ.get(name) or "").strip()


def _load_state() -> dict:
    try:
        data = json.loads(STATE_PATH.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def _save_state(state: dict) -> None:
    tmp = STATE_PATH.with_suffix(".tmp")
    tmp.write_text(json.dumps(state, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    os.replace(tmp, STATE_PATH)


def _acquire_lock() -> bool:
    try:
        fd = os.open(str(LOCK_PATH), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(str(time.time()))
        return True
    except FileExistsError:
        try:
            age = time.time() - LOCK_PATH.stat().st_mtime
        except OSError:
            age = 0
        if age > 4 * 60 * 60:
            try:
                LOCK_PATH.unlink()
            except OSError:
                return False
            return _acquire_lock()
        return False


def _release_lock() -> None:
    try:
        LOCK_PATH.unlink()
    except OSError:
        pass


def _discover_magic_categories(html: str) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    menus = soup.select("div.cdz-vertical-menu")
    menu = None
    best_count = -1
    for candidate in menus:
        count = len(candidate.select("a[href*='/catalog/category/view/']"))
        if count > best_count:
            best_count = count
            menu = candidate
    if not menu:
        raise RuntimeError("No se encontró el menú de categorías de Mercadia.")

    group = menu.find("ul", class_="groupmenu")
    if not group:
        raise RuntimeError("Mercadia no devolvió el árbol de categorías esperado.")

    categories = []
    seen = set()
    for top in group.find_all("li", recursive=False):
        direct = top.find("a", recursive=False)
        top_name = normalize_space(direct.get_text(" ", strip=True) if direct else "")
        # Everything after the MTG groups in the current menu includes Pokémon
        # and utility links. We never crawl another game's catalog.
        if top_name.casefold() == "pokemon":
            break
        links = top.select("a.menu-link[href*='/catalog/category/view/']")
        if not links:
            continue
        for link in links:
            parent_li = link.find_parent("li")
            # Only leaf set/category pages. Parent categories would duplicate all
            # products of their children and multiply traffic for no benefit.
            if parent_li and parent_li.find("ul", recursive=False):
                continue
            href = urljoin(MercadiaAdapter.BASE, link.get("href") or "")
            if not href or href in seen:
                continue
            seen.add(href)
            categories.append({
                "url": href,
                "name": normalize_space(link.get_text(" ", strip=True)) or top_name,
                "group": top_name,
            })
    if not categories:
        raise RuntimeError("No se descubrieron categorías MTG en Mercadia.")
    return categories


def _set_code_and_collector(image_url: str | None) -> tuple[str | None, str | None]:
    if not image_url:
        return None, None
    text = str(image_url)
    patterns = [
        r"[_/-]([A-Za-z0-9]{2,8})[_-]\1[-_](\d+[A-Za-z★]*)[-_]",
        r"[_/-]([A-Za-z0-9]{2,8})[-_](\d+[A-Za-z★]*)[-_]",
    ]
    for pattern in patterns:
        matches = re.findall(pattern, text, flags=re.I)
        if matches:
            code, collector = matches[-1]
            return code.upper(), collector
    return None, None


def _parse_product_rows(adapter: MercadiaAdapter, html: str, category: dict) -> tuple[list[dict], bool]:
    soup = BeautifulSoup(html, "html.parser")
    rows = []
    seen = set()
    for item in soup.select("li.product-item"):
        link = item.select_one("a.product-item-link")
        if not link or not link.get("href"):
            continue
        # Magento only renders an add-to-cart form for products currently
        # salable in this storefront. This lets the catalog sync stay list-page
        # only: no product detail request is needed.
        cart_form = item.select_one("form[data-role='tocart-form'], form[data-product-sku]")
        if not cart_form:
            continue

        name = normalize_space(link.get_text(" ", strip=True))
        if not name:
            continue
        url = urljoin(adapter.BASE, link.get("href"))
        sku_node = item.select_one(".product-item-sku .value")
        sku = normalize_space(sku_node.get_text(" ", strip=True) if sku_node else "") or cart_form.get("data-product-sku")
        product_id = None
        hidden_id = cart_form.select_one("input[name='product'][value]")
        if hidden_id:
            product_id = hidden_id.get("value")
        if not product_id:
            match = re.search(r"/id/(\d+)/", url)
            if match:
                product_id = match.group(1)

        price_node = item.select_one("[data-price-type='finalPrice'][data-price-amount], [data-price-amount]")
        price = price_node.get("data-price-amount") if price_node else None
        image_node = item.select_one("img.main-img, img.product-image-photo")
        image = None
        if image_node:
            image = image_node.get("src") or image_node.get("data-src") or image_node.get("data-original")
            if image:
                image = urljoin(adapter.BASE, image)

        desc_node = item.select_one(".product-item-description")
        description = normalize_space(desc_node.get_text(" ", strip=True) if desc_node else "")
        meta = adapter._description_meta(description, name)
        image_set_code, image_collector = _set_code_and_collector(image)
        set_code = image_set_code or meta.get("set_code")
        collector = image_collector or adapter._collector_from_image(image, set_code)

        key = str(product_id or sku or url)
        if key in seen:
            continue
        seen.add(key)
        rows.append({
            "store": "Mercadia",
            "card_name": name,
            "set_name": category.get("name") or set_code,
            "set_code": set_code,
            "collector_number": collector,
            "language": meta.get("language"),
            "condition": meta.get("condition"),
            "finish": meta.get("finish"),
            "style": None,
            "price": str(price) if price not in (None, "") else None,
            "currency": "ARS",
            "stock": None,
            "available": True,
            "url": url,
            "image_url": image,
            "product_id": product_id,
            "variant_id": None,
            "sku": sku,
            "scryfall_id": None,
        })

    has_next = bool(soup.select_one("a.action.next[href], li.pages-item-next a[href]"))
    return rows, has_next


def _crawl_category(adapter: MercadiaAdapter, category: dict, page_callback=None) -> list[dict]:
    out = []
    seen = set()
    for page in range(1, MAX_PAGES_PER_CATEGORY + 1):
        response = adapter.http.get(
            category["url"],
            params={"product_list_limit": PAGE_LIMIT, "p": page},
        )
        rows, has_next = _parse_product_rows(adapter, response.text, category)
        for row in rows:
            key = str(row.get("product_id") or row.get("sku") or row.get("url"))
            if key in seen:
                continue
            seen.add(key)
            out.append(row)
        if page_callback:
            page_callback(page, len(out), has_next)
        if not has_next:
            break
        if REQUEST_DELAY:
            time.sleep(REQUEST_DELAY)
    return out


def _catalog_union(category_state: dict) -> list[dict]:
    unique = {}
    for item in category_state.values():
        for row in item.get("rows") or []:
            key = str(row.get("product_id") or row.get("sku") or row.get("url"))
            if key:
                unique[key] = row
    return list(unique.values())


def _upload_catalog(base_url: str, headers: dict, rows: list[dict], metadata: dict) -> None:
    sync_id = f"{int(time.time())}-{uuid.uuid4().hex[:10]}"
    start = requests.post(
        f"{base_url}/api/bridge/mercadia/catalog/start/",
        json={"sync_id": sync_id, "metadata": metadata},
        headers=headers,
        timeout=45,
    )
    start.raise_for_status()

    total_batches = max(1, (len(rows) + BATCH_SIZE - 1) // BATCH_SIZE)
    upload_started = time.time()
    print(f"[FASE 2/2] Subiendo {len(rows)} publicaciones a Fetchuccini en {total_batches} lote(s)...", flush=True)
    for index in range(0, len(rows), BATCH_SIZE):
        batch = rows[index:index + BATCH_SIZE]
        pushed = requests.post(
            f"{base_url}/api/bridge/mercadia/catalog/batch/",
            json={"sync_id": sync_id, "results": batch},
            headers=headers,
            timeout=60,
        )
        pushed.raise_for_status()
        batch_number = index // BATCH_SIZE + 1
        uploaded = min(index + len(batch), len(rows))
        _print_progress(
            "SUBIDA",
            batch_number,
            total_batches,
            upload_started,
            detail=f"{uploaded}/{len(rows)} publicaciones",
        )

    finish = requests.post(
        f"{base_url}/api/bridge/mercadia/catalog/finish/",
        json={"sync_id": sync_id, "metadata": metadata},
        headers=headers,
        timeout=90,
    )
    if finish.status_code == 409:
        try:
            detail = (finish.json() or {}).get("error") or finish.text
        except ValueError:
            detail = finish.text
        raise RuntimeError(f"Railway conservó el catálogo anterior: {detail}")
    finish.raise_for_status()
    data = finish.json()
    previous = data.get("previous_count")
    previous_text = f" (anterior: {previous})" if previous not in (None, 0) else ""
    print(f"[OK] Catálogo publicado: {data.get('count', len(rows))} publicaciones en stock{previous_text}.")


def main() -> int:
    base_url = _env("FETCHUCCINI_URL").rstrip("/")
    bridge_key = _env("MERCADIA_BRIDGE_KEY")
    if not base_url or not bridge_key:
        print("[ERROR] Faltan FETCHUCCINI_URL o MERCADIA_BRIDGE_KEY. Ejecutá mercadia_bridge_setup.bat.")
        return 2
    if not _acquire_lock():
        print("[INFO] Ya hay una sincronización de catálogo en ejecución. Salgo sin iniciar otra.")
        return 0

    started = time.time()
    headers = {
        "X-Fetchuccini-Bridge-Key": bridge_key,
        "Accept": "application/json",
        "Content-Type": "application/json",
        "User-Agent": "Fetchuccini-Mercadia-Catalog/1.0",
    }
    try:
        adapter = MercadiaAdapter()
        adapter.http.timeout = 18
        state = _load_state()
        previous_categories = state.get("categories") if isinstance(state.get("categories"), dict) else {}

        print("[INFO] Descubriendo categorías MTG de Mercadia...")
        seed = adapter.http.get(
            adapter.SEARCH,
            params={"q": SEED_QUERY, "product_list_limit": PAGE_LIMIT, "p": 1},
        )
        categories = _discover_magic_categories(seed.text)
        print(f"[INFO] {len(categories)} categorías MTG descubiertas.")

        new_categories = {}
        failures = 0
        category_total = len(categories)
        crawl_started = time.time()
        collected_rows = 0
        print("[FASE 1/2] Recorriendo categorías y publicaciones de Mercadia...", flush=True)
        _print_progress("CATÁLOGO", 0, category_total, crawl_started, detail="iniciando")
        for index, category in enumerate(categories, start=1):
            url = category["url"]
            old = previous_categories.get(url) or {}
            print(f"\n[{index}/{category_total}] {category['name']}", flush=True)

            def _page_progress(page: int, row_count: int, has_next: bool) -> None:
                # Show the first page, every fifth page and the final page so a
                # large category never looks frozen while it is being crawled.
                if page == 1 or page % 5 == 0 or not has_next:
                    state = "continúa" if has_next else "fin"
                    print(
                        f"    [PÁGINA {page}] {row_count} publicación(es) acumuladas · {state}",
                        flush=True,
                    )

            try:
                rows = _crawl_category(adapter, category, page_callback=_page_progress)
                new_categories[url] = {
                    "name": category["name"],
                    "group": category.get("group"),
                    "synced_at": time.time(),
                    "rows": rows,
                }
                collected_rows += len(rows)
                print(f"    [OK] {len(rows)} publicación(es) en stock", flush=True)
            except Exception as exc:
                failures += 1
                if old:
                    new_categories[url] = old
                    collected_rows += len(old.get("rows") or [])
                    print(f"    [WARN] {type(exc).__name__}: {exc} — conservo el último snapshot local", flush=True)
                else:
                    print(f"    [ERROR] {type(exc).__name__}: {exc}", flush=True)

            _print_progress(
                "CATÁLOGO",
                index,
                category_total,
                crawl_started,
                detail=f"~{collected_rows} publicaciones recopiladas · {failures} error(es)",
            )
            if index % 10 == 0:
                checkpoint_categories = dict(previous_categories)
                checkpoint_categories.update(new_categories)
                _save_state({
                    "version": 1,
                    "updated_at": time.time(),
                    "categories": checkpoint_categories,
                })
            if REQUEST_DELAY:
                time.sleep(REQUEST_DELAY)

        local_state = {
            "version": 1,
            "updated_at": time.time(),
            "categories": new_categories,
        }
        _save_state(local_state)
        rows = _catalog_union(new_categories)
        elapsed = int(time.time() - started)
        print(f"[INFO] Catálogo local: {len(rows)} publicaciones únicas. Subiendo a Fetchuccini...")
        metadata = {
            "category_count": len(categories),
            "failed_category_count": failures,
            "crawl_seconds": elapsed,
            "source": "mercadia-windows-catalog",
        }
        _upload_catalog(base_url, headers, rows, metadata)
        if failures:
            print(f"[WARN] {failures} categoría(s) fallaron; se conservaron datos anteriores cuando existían.")
        print(f"[OK] Sincronización completa terminada en {elapsed // 60}m {elapsed % 60}s.")
        return 0
    except requests.HTTPError as exc:
        if exc.response is not None and exc.response.status_code == 403 and "fetchuccini" in str(exc.request.url).lower():
            print("[ERROR] Railway rechazó la clave del bridge. Revisá MERCADIA_BRIDGE_KEY.")
        else:
            print(f"[ERROR] HTTPError: {exc}")
        return 1
    except Exception as exc:
        print(f"[ERROR] {type(exc).__name__}: {exc}")
        return 1
    finally:
        _release_lock()


if __name__ == "__main__":
    raise SystemExit(main())
