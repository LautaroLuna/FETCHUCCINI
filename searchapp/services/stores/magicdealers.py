import re
import time
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

from .base import StoreAdapter
from ..models import Listing
from ..http import SearchBudgetExceeded
from ..utils import as_int, exactish_card_name, normalize_space, parse_ars


class MagicDealersAdapter(StoreAdapter):
    key = "magicdealers"
    name = "MagicDealers"
    BASE = "https://www.magicdealersstore.com"
    SEARCH = f"{BASE}/products/search"

    # MagicDealers starts returning 503s when detail pages are requested too
    # aggressively. Two workers keeps the search responsive without hammering it.
    # CrystalCommerce / MagicDealers is occasionally flaky at the TLS layer and
    # may close a connection with SSL EOF before sending the response. Keep this
    # adapter deliberately conservative and retry search pages with a fresh
    # connection before giving up.
    DETAIL_WORKERS = 1
    DETAIL_DELAY_SECONDS = 0.35
    SEARCH_ATTEMPTS = 2
    SEARCH_TIMEOUT_SECONDS = 9
    SEARCH_BACKOFF_SECONDS = 0.35
    MAX_SEARCH_PAGES = 8

    SEARCH_HEADERS = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/152.0.0.0 Safari/537.36"
        ),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Accept-Language": "es-AR,es;q=0.9,en-US;q=0.8,en;q=0.7",
        # Avoid reusing a TLS connection that the origin may have already closed.
        "Connection": "close",
    }

    def _search_get(self, url: str, **kwargs):
        """Fetch a MagicDealers search page with a small, bounded retry budget.

        v0.27 accidentally stacked two retry layers: HttpClient/urllib3 could
        retry a request three times and this method could repeat that whole
        sequence five times. On a flaky TLS/503 response that made a single
        MagicDealers search take 40-60 seconds.

        Here we intentionally bypass HttpClient's automatic retry layer for
        this origin and allow at most two fresh connections. Partial pagination
        results are still preserved by ``search`` below.
        """
        last_error = None
        params = kwargs.pop("params", None)
        extra_headers = kwargs.pop("headers", {}) or {}
        headers = dict(self.SEARCH_HEADERS)
        headers.update(extra_headers)

        for attempt in range(1, self.SEARCH_ATTEMPTS + 1):
            try:
                response = requests.get(
                    url,
                    params=params,
                    headers=headers,
                    timeout=self.http.reserve_request(self.SEARCH_TIMEOUT_SECONDS),
                    **kwargs,
                )
                response.raise_for_status()
                return response
            except SearchBudgetExceeded:
                raise
            except requests.RequestException as exc:
                last_error = exc
                if attempt < self.SEARCH_ATTEMPTS:
                    time.sleep(self.SEARCH_BACKOFF_SECONDS * attempt)

        raise last_error

    def _detail_fields(self, url: str):
        """Fetch optional metadata from a product page.

        Price/stock/condition/language already come from the search page. Detail
        pages are only an enrichment step (set, collector number, finish), so a
        temporary 429/5xx must never make the whole store disappear.
        """
        try:
            time.sleep(self.DETAIL_DELAY_SECONDS)
            response = self.http.get(url)
        except requests.RequestException:
            return {}

        soup = BeautifulSoup(response.text, "html.parser")
        text = soup.get_text("\n", strip=True)
        fields = {}
        for label in ("Finish", "Card Number", "Set Name"):
            m = re.search(rf"{re.escape(label)}\s*:?\s*\n?\s*([^\n]+)", text, flags=re.I)
            if m:
                fields[label] = normalize_space(m.group(1))
        return fields

    def _parse_page(self, html: str, card_name: str):
        soup = BeautifulSoup(html, "html.parser")
        rows = []
        seen = set()
        for a in soup.select("a[href*='/catalog/']"):
            href = a.get("href")
            title = normalize_space(a.get_text(" ", strip=True))
            if not href or not exactish_card_name(title, card_name):
                continue
            full = urljoin(self.BASE, href)
            if full in seen:
                continue
            seen.add(full)
            # CrystalCommerce repeats links in several responsive layouts. Start
            # from the complete product card when possible so category/set, stock,
            # price and image all come from the same product.
            container = a.find_parent("li", class_="product") or a.find_parent(class_="image-meta") or a
            if container is a:
                for _ in range(6):
                    parent = container.parent
                    if not parent:
                        break
                    ptext = normalize_space(parent.get_text(" ", strip=True))
                    if "In Stock" in ptext or "ARS$" in ptext:
                        container = parent
                        break
                    container = parent
            text = normalize_space(container.get_text(" ", strip=True))
            stock_m = re.search(r"(\d+)\s+In Stock", text, flags=re.I)
            price_m = re.search(r"ARS\$\s*([0-9.,]+)", text, flags=re.I)
            cond_m = re.search(
                r"(Near Mint|Lightly Played|Moderately Played|Played|Heavily Played|Damaged)\s*,\s*"
                r"(English|Spanish|Japanese|Portuguese|Italian|French|German)",
                text,
                flags=re.I,
            )
            variant_id = None
            product_id = None
            for tag in container.find_all(True):
                for key, val in tag.attrs.items():
                    lk = key.casefold()
                    if "variant" in lk and str(val).isdigit():
                        variant_id = val
                    if "product" in lk and str(val).isdigit():
                        product_id = val
            m = re.search(r"/(\d+)(?:\?.*)?$", full)
            if m:
                product_id = product_id or m.group(1)
            # CrystalCommerce already exposes the card image on the search page.
            # Grab it from any anchor pointing to this exact product URL so images
            # still work even when the detail-page enrichment is throttled/503.
            image_url = None
            for link in soup.find_all("a", href=href):
                img = link.find("img")
                if not img:
                    continue
                image_url = (
                    img.get("src")
                    or img.get("data-src")
                    or img.get("data-original")
                    or img.get("data-lazy-src")
                )
                if image_url:
                    image_url = urljoin(self.BASE, image_url)
                    break

            category = container.select_one(".category")
            set_name = normalize_space(category.get_text(" ", strip=True)) if category else None

            rows.append({
                "title": title,
                "url": full,
                "image_url": image_url,
                "set_name": set_name,
                "stock": as_int(stock_m.group(1)) if stock_m else None,
                "price": parse_ars(price_m.group(1)) if price_m else None,
                "condition": cond_m.group(1) if cond_m else None,
                "language": cond_m.group(2) if cond_m else None,
                "variant_id": variant_id,
                "product_id": product_id,
            })
        next_link = soup.select_one("a[rel='next']")
        return rows, (next_link.get("href") if next_link else None)

    def _build_listing(self, card_name: str, row: dict) -> Listing:
        # Public-hosting mode: the search page already has the fields needed for
        # comparison. Do not open a detail page for every in-stock result: that
        # made MagicDealers take several minutes and increased TLS/503 failures.
        # Set/price/condition/language/stock/image remain available immediately.
        details = {}
        title = row["title"]
        style = title.split(" - ", 1)[1] if " - " in title else None
        display_name = title.split(" - ", 1)[0].strip() or card_name
        inferred_finish = "Foil" if "foil" in title.casefold() else None
        return Listing(
            store=self.name,
            card_name=display_name,
            set_name=details.get("Set Name") or row.get("set_name"),
            collector_number=details.get("Card Number"),
            language=row["language"],
            condition=row["condition"],
            finish=details.get("Finish") or inferred_finish,
            style=style,
            price=row["price"],
            currency="ARS",
            stock=row["stock"],
            available=(row["stock"] or 0) > 0 if row["stock"] is not None else None,
            url=row["url"],
            image_url=row.get("image_url"),
            product_id=row["product_id"],
            variant_id=row["variant_id"],
        )

    def search(self, card_name: str) -> list[Listing]:
        rows = []
        page = 1
        next_url = None
        while page <= self.MAX_SEARCH_PAGES:
            try:
                if next_url:
                    html = self._search_get(urljoin(self.BASE, next_url)).text
                else:
                    html = self._search_get(
                        self.SEARCH,
                        params={"c": 8, "q": card_name, "page": page},
                    ).text
            except requests.RequestException as exc:
                # If a later pagination request fails, keep the useful pages
                # already collected instead of dropping MagicDealers entirely.
                if rows:
                    self.mark_partial(exc)
                    break
                raise

            found, next_url = self._parse_page(html, card_name)
            # CrystalCommerce sorts search results by relevance. Once a page has
            # no card whose name starts with the requested prefix, continuing
            # through the remaining result pages only adds latency.
            if not found:
                break
            rows.extend(found)
            if not next_url:
                break
            page += 1

        if not rows:
            return []

        # _build_listing no longer performs network I/O, so a thread pool only
        # adds overhead. Build the normalized rows directly and keep stock-only
        # publications, which is Fetchuccini's global policy.
        listings = []
        for row in rows:
            try:
                item = self._build_listing(card_name, row)
            except Exception:
                title = row["title"]
                display_name = title.split(" - ", 1)[0].strip() or card_name
                item = Listing(
                    store=self.name,
                    card_name=display_name,
                    set_name=row.get("set_name"),
                    language=row["language"],
                    condition=row["condition"],
                    finish="Foil" if "foil" in title.casefold() else None,
                    style=title.split(" - ", 1)[1] if " - " in title else None,
                    price=row["price"],
                    currency="ARS",
                    stock=row["stock"],
                    available=(row["stock"] or 0) > 0 if row["stock"] is not None else None,
                    url=row["url"],
                    image_url=row.get("image_url"),
                    product_id=row["product_id"],
                    variant_id=row["variant_id"],
                )
            if item.available and (item.stock is None or item.stock > 0):
                listings.append(item)

        return listings
