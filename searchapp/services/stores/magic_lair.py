import re
import time
from decimal import Decimal
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

from .base import StoreAdapter
from ..models import Listing
from ..utils import as_int, exactish_card_name, normalize_space


class MagicLairAdapter(StoreAdapter):
    key = "magic_lair"
    name = "Magic Lair"
    BASE = "https://www.lair.com.ar"
    MAX_PAGES = 9
    MAX_LEADING_EMPTY_PAGES = 3
    PAGE_DELAY_SECONDS = 0.20

    def _parse_page(self, html: str, card_name: str) -> list[Listing]:
        """Parse Shopify search cards without opening every product page.

        Magic Lair exposes variant id, condition, stock and price directly in
        each search-card chip. Reading those fields from the search results is
        dramatically cheaper than doing one /products/<handle>.js request per
        product, and avoids the 429s seen from public hosting providers.
        """
        soup = BeautifulSoup(html or "", "html.parser")
        out: list[Listing] = []

        for card in soup.select(".productCard__card"):
            title_link = card.select_one(".productCard__title a") or card.select_one("a[href*='/products/']")
            if not title_link:
                continue

            title = normalize_space(title_link.get_text(" ", strip=True) or title_link.get("title"))
            if not exactish_card_name(title, card_name):
                continue

            href = title_link.get("href") or ""
            product_url = urljoin(self.BASE, href.split("?", 1)[0])
            product_id = card.get("data-productid")

            set_node = card.select_one(".productCard__setName")
            set_name = normalize_space(set_node.get_text(" ", strip=True)) if set_node else None

            image = None
            img = card.select_one("img")
            if img:
                image = img.get("data-src") or img.get("src")
                if image and image.startswith("//"):
                    image = "https:" + image
                elif image:
                    image = urljoin(self.BASE, image)

            style = None
            style_match = re.search(r"\(([^)]+)\)\s*$", title)
            if style_match:
                style = normalize_space(style_match.group(1))
            display_name = re.sub(r"\s+\([^)]+\)\s*$", "", title).strip() or title

            chips = card.select(".productChip[data-variantid]")
            for chip in chips:
                variant_id = chip.get("data-variantid")
                variant_title = normalize_space(chip.get("data-varianttitle") or chip.get_text(" ", strip=True))
                qty = as_int(chip.get("data-variantqty"))
                available_attr = str(chip.get("data-variantavailable") or "").casefold()
                available = available_attr == "true"
                if qty is not None:
                    available = qty > 0

                raw_price = chip.get("data-variantprice")
                try:
                    price = Decimal(str(raw_price)) / Decimal("100") if raw_price not in (None, "") else None
                except Exception:
                    price = None

                is_foil = "foil" in variant_title.casefold()
                finish = "Foil" if is_foil else "Normal"
                condition = re.sub(r"\s+Foil$", "", variant_title, flags=re.I).strip() or None

                out.append(Listing(
                    store=self.name,
                    card_name=display_name,
                    set_name=set_name,
                    collector_number=None,
                    language=None,
                    condition=condition,
                    finish=finish,
                    style=style,
                    price=price,
                    currency="ARS",
                    stock=qty,
                    available=available,
                    url=f"{product_url}?variant={variant_id}" if variant_id else product_url,
                    image_url=image,
                    product_id=product_id,
                    variant_id=variant_id,
                ))

        return out

    @staticmethod
    def _has_next_page(html: str, current_page: int) -> bool:
        """Return whether Shopify exposes a real next page link.

        Magic Lair renders an ``ol.pagination`` with a text ``Next`` link.
        Using the page controls lets us stop immediately at the real end instead
        of blindly walking all ``MAX_PAGES``.
        """
        soup = BeautifulSoup(html or "", "html.parser")
        pagination = soup.select_one("ol.pagination, .pagination")
        if not pagination:
            return False
        for link in pagination.select("a[href]"):
            href = link.get("href") or ""
            label = normalize_space(link.get_text(" ", strip=True)).casefold()
            page_match = re.search(r"(?:[?&])page=(\d+)", href)
            if page_match and int(page_match.group(1)) > current_page:
                return True
            if label.startswith("next") and not page_match:
                return True
        return False

    def search(self, card_name: str) -> list[Listing]:
        out: list[Listing] = []
        seen_variants = set()
        matched_on_previous_page = False
        leading_empty_pages = 0

        for page in range(1, self.MAX_PAGES + 1):
            try:
                response = self.http.get(
                    f"{self.BASE}/search",
                    params={"q": card_name, "type": "product", "page": page},
                )
            except requests.RequestException as exc:
                # If a later page is throttled/budget-limited, keep the useful
                # results already collected and expose that they are partial.
                if out:
                    self.mark_partial(exc)
                    break
                raise

            page_rows = self._parse_page(response.text, card_name)
            added = 0
            for row in page_rows:
                stable_id = str(row.variant_id or row.url)
                if stable_id in seen_variants:
                    continue
                seen_variants.add(stable_id)
                out.append(row)
                added += 1

            # Stop as soon as Shopify says there is no next page. For very broad
            # searches with no exact/prefix match, cap leading empty work at three
            # pages so one missing card cannot fan out into nine remote requests.
            has_next_page = self._has_next_page(response.text, page)
            if page_rows:
                leading_empty_pages = 0
            else:
                leading_empty_pages += 1

            if not has_next_page:
                break
            if not page_rows and matched_on_previous_page:
                break
            if not out and leading_empty_pages >= self.MAX_LEADING_EMPTY_PAGES:
                break
            matched_on_previous_page = bool(page_rows)

            if page < self.MAX_PAGES:
                time.sleep(self.PAGE_DELAY_SECONDS)

        return out
