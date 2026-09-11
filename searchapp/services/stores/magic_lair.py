import re
from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal
from bs4 import BeautifulSoup
from .base import StoreAdapter
from ..models import Listing
from ..utils import as_int, exactish_card_name, normalize_space


class MagicLairAdapter(StoreAdapter):
    key = "magic_lair"
    name = "Magic Lair"
    BASE = "https://www.lair.com.ar"
    PRODUCT_WORKERS = 4

    def _search_page(self, card_name: str, page: int):
        html = self.http.get(f"{self.BASE}/search", params={"q": f'"{card_name}"', "type": "product", "page": page}).text
        soup = BeautifulSoup(html, "html.parser")
        handles = {}
        for a in soup.select("a[href*='/products/']"):
            href = a.get("href") or ""
            title = normalize_space(a.get("title") or a.get_text(" ", strip=True))
            if "/products/" not in href:
                continue
            handle = href.split("/products/", 1)[1].split("?", 1)[0].strip("/")
            if not handle:
                continue
            if exactish_card_name(title, card_name) or card_name.casefold().replace(" ", "-") in handle.casefold():
                handles[handle] = title
        # Variant stock is embedded in the rendered search cards.
        stock_by_variant = {}
        for tag in soup.find_all(True):
            attrs = {k.lower().replace("_", "-"): v for k, v in tag.attrs.items()}
            variant_id = attrs.get("data-variant-id") or attrs.get("data-variantid")
            if variant_id:
                qty = attrs.get("data-variant-qty") or attrs.get("data-variantqty")
                stock_by_variant[str(variant_id)] = as_int(qty)
        return handles, stock_by_variant

    def _set_from_description(self, description: str | None) -> str | None:
        soup = BeautifulSoup(description or "", "html.parser")
        for row in soup.select("tr"):
            cells = row.find_all("td")
            if len(cells) >= 2 and normalize_space(cells[0].get_text()).casefold().rstrip(":") == "set":
                return normalize_space(cells[1].get_text())
        return None

    def _parse_sku(self, sku: str | None):
        if not sku:
            return None, None, None, None
        parts = sku.split("-")
        if len(parts) < 5:
            return None, None, None, None
        set_code, collector, language, finish_code = parts[:4]
        finish = {"NF": "Normal", "FO": "Foil"}.get(finish_code, finish_code)
        return set_code, collector, language, finish

    def _product_rows(self, handle: str, card_name: str, stock_map: dict) -> list[Listing]:
        data = self.http.get(f"{self.BASE}/products/{handle}.js").json()
        product_title = data.get("title") or card_name
        plain_name = re.sub(r"\s*\[[^\]]+\]\s*$", "", product_title).strip()
        if not exactish_card_name(plain_name, card_name):
            return []

        set_name = self._set_from_description(data.get("description"))
        out = []
        for variant in data.get("variants") or []:
            set_code, collector, language, sku_finish = self._parse_sku(variant.get("sku"))
            title = variant.get("title") or ""
            finish = "Foil" if "foil" in title.casefold() else sku_finish or "Normal"
            condition = re.sub(r"\s+Foil$", "", title, flags=re.I).strip()
            variant_id = variant.get("id")
            stock = stock_map.get(str(variant_id))
            available = bool(variant.get("available"))
            if stock is not None:
                available = stock > 0
            price = variant.get("price")
            image = data.get("featured_image") or ""
            if image.startswith("//"):
                image = "https:" + image
            out.append(Listing(
                store=self.name,
                card_name=plain_name,
                set_name=set_name,
                set_code=set_code,
                collector_number=collector,
                language=language,
                condition=condition,
                finish=finish,
                price=(Decimal(str(price)) / Decimal("100")) if price is not None else None,
                currency="ARS",
                stock=stock,
                available=available,
                url=f"{self.BASE}/products/{handle}?variant={variant_id}",
                image_url=image,
                product_id=data.get("id"),
                variant_id=variant_id,
                sku=variant.get("sku"),
            ))
        return out

    def search(self, card_name: str) -> list[Listing]:
        handles = {}
        stock_map = {}
        for page in range(1, 10):
            page_handles, page_stock = self._search_page(card_name, page)
            if not page_handles:
                break
            before = len(handles)
            handles.update(page_handles)
            stock_map.update(page_stock)
            if len(handles) == before:
                break

        out = []
        with ThreadPoolExecutor(max_workers=self.PRODUCT_WORKERS) as pool:
            for rows in pool.map(lambda handle: self._product_rows(handle, card_name, stock_map), handles):
                out.extend(rows)
        return out
