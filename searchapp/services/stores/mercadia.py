import re
from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal
from urllib.parse import urljoin
from bs4 import BeautifulSoup
from .base import StoreAdapter
from ..models import Listing
from ..utils import as_int, exactish_card_name, normalize_space


class MercadiaAdapter(StoreAdapter):
    key = "mercadia"
    name = "Mercadia"
    BASE = "https://mercadiacity.com"
    SEARCH = f"{BASE}/index.php/catalogsearch/result/"
    DETAIL_WORKERS = 4

    def _product_links(self, html: str, card_name: str):
        soup = BeautifulSoup(html, "html.parser")
        found = []
        for a in soup.select("a.product-item-link, a[href*='/catalog/product/view/']"):
            name = normalize_space(a.get_text(" ", strip=True))
            href = a.get("href")
            if href and exactish_card_name(name, card_name):
                found.append((name, href))
        has_next = bool(soup.select_one("a.action.next, a.pages-item-next, a[title='Next']"))
        return list(dict.fromkeys(found)), has_next

    def _attributes(self, soup: BeautifulSoup) -> dict[str, str]:
        attrs = {}
        for row in soup.select("table tr, .additional-attributes-wrapper tr"):
            cells = row.find_all(["th", "td"])
            if len(cells) >= 2:
                key = normalize_space(cells[0].get_text(" ", strip=True)).rstrip(":")
                val = normalize_space(cells[1].get_text(" ", strip=True))
                if key and val:
                    attrs[key.casefold()] = val
        return attrs

    def _detail(self, name: str, url: str) -> Listing:
        soup = BeautifulSoup(self.http.get(url).text, "html.parser")
        attrs = self._attributes(soup)
        price_node = soup.select_one("[data-price-type='finalPrice'][data-price-amount], [data-price-amount]")
        price = Decimal(price_node.get("data-price-amount")) if price_node and price_node.get("data-price-amount") else None
        stock = None
        stock_node = soup.select_one(".availability.only strong")
        if stock_node:
            stock = as_int(re.sub(r"\D", "", stock_node.get_text()))
        available = bool(soup.select_one(".stock.available"))
        if stock is not None:
            available = stock > 0
        sku = None
        form = soup.select_one("form[data-product-sku]")
        if form:
            sku = form.get("data-product-sku")
        product_id = None
        m = re.search(r"/id/(\d+)/", url)
        if m:
            product_id = m.group(1)
        image = None
        og = soup.select_one("meta[property='og:image']")
        if og:
            image = og.get("content")
        currency = "ARS"
        meta_currency = soup.select_one("meta[property='product:price:currency']")
        if meta_currency and meta_currency.get("content"):
            currency = meta_currency["content"]
        return Listing(
            store=self.name,
            card_name=attrs.get("name", name),
            set_name=attrs.get("edition") or attrs.get("edición"),
            set_code=attrs.get("edition code") or attrs.get("código de edición"),
            collector_number=attrs.get("number") or attrs.get("número"),
            language=attrs.get("language") or attrs.get("idioma"),
            condition=attrs.get("condition") or attrs.get("condición"),
            finish=attrs.get("foil?") or attrs.get("foil") or attrs.get("acabado"),
            price=price,
            currency=currency,
            stock=stock,
            available=available,
            url=url,
            image_url=image,
            product_id=product_id,
            sku=sku,
        )

    def search(self, card_name: str) -> list[Listing]:
        candidates = []
        seen = set()
        page = 1
        while page <= 50:
            html = self.http.get(self.SEARCH, params={"q": card_name, "product_list_limit": 36, "p": page}).text
            links, has_next = self._product_links(html, card_name)
            for name, url in links:
                full = urljoin(self.BASE, url)
                if full not in seen:
                    seen.add(full)
                    candidates.append((name, full))
            if not has_next or not links:
                break
            page += 1

        with ThreadPoolExecutor(max_workers=self.DETAIL_WORKERS) as pool:
            return list(pool.map(lambda pair: self._detail(*pair), candidates))
