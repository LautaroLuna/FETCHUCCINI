import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

from .base import StoreAdapter
from ..models import Listing
from ..http import HttpClient
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
    SEARCH_ATTEMPTS = 5
    SEARCH_TIMEOUT_SECONDS = 18
    SEARCH_BACKOFF_SECONDS = 0.9

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
        """Fetch a MagicDealers search page defensively.

        The store sometimes terminates HTTPS connections with
        SSL: UNEXPECTED_EOF_WHILE_READING. urllib3 already retries a couple of
        times globally, but for this specific origin we also retry with a fresh
        Session/connection and a short progressive backoff.
        """
        last_error = None
        for attempt in range(1, self.SEARCH_ATTEMPTS + 1):
            try:
                headers = dict(self.SEARCH_HEADERS)
                headers.update(kwargs.pop("headers", {}) or {})
                return self.http.get(
                    url,
                    timeout=self.SEARCH_TIMEOUT_SECONDS,
                    headers=headers,
                    **kwargs,
                )
            except requests.RequestException as exc:
                last_error = exc
                if attempt >= self.SEARCH_ATTEMPTS:
                    break

                # Throw away the old connection pool. This is important for the
                # intermittent TLS EOF issue seen on this store.
                try:
                    self.http.session.close()
                except Exception:
                    pass
                self.http = HttpClient(timeout=self.SEARCH_TIMEOUT_SECONDS)
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
        # The search page already contains the information needed for comparing
        # price/stock. Product detail pages are much slower and are the part of
        # MagicDealers most likely to throttle us, so only enrich listings that
        # actually have stock. This cuts dozens of unnecessary requests.
        details = self._detail_fields(row["url"]) if (row.get("stock") or 0) > 0 else {}
        title = row["title"]
        style = title.split(" - ", 1)[1] if " - " in title else None
        inferred_finish = "Foil" if "foil" in title.casefold() else None
        return Listing(
            store=self.name,
            card_name=card_name,
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
        while page <= 30:
            try:
                if next_url:
                    html = self._search_get(urljoin(self.BASE, next_url)).text
                else:
                    html = self._search_get(
                        self.SEARCH,
                        params={"c": 8, "q": card_name, "page": page},
                    ).text
            except requests.RequestException:
                # If a later pagination request fails, keep the useful pages
                # already collected instead of dropping MagicDealers entirely.
                if rows:
                    break
                raise

            found, next_url = self._parse_page(html, card_name)
            rows.extend(found)
            if not next_url:
                break
            page += 1

        if not rows:
            return []

        # Preserve partial results even when one or more detail pages fail.
        listings = [None] * len(rows)
        with ThreadPoolExecutor(max_workers=self.DETAIL_WORKERS) as pool:
            future_map = {
                pool.submit(self._build_listing, card_name, row): idx
                for idx, row in enumerate(rows)
            }
            for future in as_completed(future_map):
                idx = future_map[future]
                try:
                    listings[idx] = future.result()
                except Exception:
                    # Last-resort fallback: return the useful search-page data.
                    row = rows[idx]
                    title = row["title"]
                    listings[idx] = Listing(
                        store=self.name,
                        card_name=card_name,
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

        return [item for item in listings if item is not None]
