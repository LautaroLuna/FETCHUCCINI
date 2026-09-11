import json
import re
from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

from .base import StoreAdapter
from ..models import Listing
from ..utils import as_int, exactish_card_name, normalize_space


class MercadiaAdapter(StoreAdapter):
    key = "mercadia"
    name = "Mercadia"
    BASE = "https://mercadiacity.com"
    SEARCH = f"{BASE}/index.php/catalogsearch/result/"
    GRAPHQL_ENDPOINTS = (f"{BASE}/graphql", f"{BASE}/index.php/graphql")
    AUTOCOMPLETE = f"{BASE}/index.php/mageworx_searchsuiteautocomplete/ajax/index/"
    DETAIL_WORKERS = 2

    # Magento's public storefront GraphQL is the preferred online path. The
    # normal catalog search page is protected against some datacenter IPs.
    GRAPHQL_QUERY = """
    query FetchucciniSearch($term:String!,$page:Int!,$pageSize:Int!) {
      products(search:$term,currentPage:$page,pageSize:$pageSize) {
        total_count
        page_info { current_page total_pages page_size }
        items {
          id sku name url_key stock_status only_x_left_in_stock
          description { html }
          small_image { url label }
          price_range {
            minimum_price { final_price { value currency } }
          }
        }
      }
    }
    """

    # If an older Magento schema rejects only_x_left_in_stock, retry with a
    # minimal query that is supported across many 2.4.x storefront versions.
    GRAPHQL_QUERY_BASIC = """
    query FetchucciniSearch($term:String!,$page:Int!,$pageSize:Int!) {
      products(search:$term,currentPage:$page,pageSize:$pageSize) {
        total_count
        page_info { current_page total_pages page_size }
        items {
          id sku name url_key stock_status
          description { html }
          small_image { url label }
          price_range {
            minimum_price { final_price { value currency } }
          }
        }
      }
    }
    """

    LANGUAGE_CODES = {
        "EN": "Inglés", "SP": "Español", "ES": "Español", "XX": "Aleatorio",
        "JP": "Japonés", "KO": "Coreano", "CO": "Coreano", "PT": "Portugués",
        "FR": "Francés", "CH": "Chino", "IT": "Italiano", "AL": "Alemán", "DE": "Alemán", "RU": "Ruso",
    }
    CONDITION_CODES = {
        "NM": "Near Mint", "EX": "Excelente", "EX-NM": "Excelente",
        "LP": "Lightly Played", "SP": "Jugada (SP)", "MP": "Moderately Played", "HP": "Heavily Played",
    }

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

    def _description_meta(self, html: str | None, card_name: str) -> dict:
        text = normalize_space(BeautifulSoup(html or "", "html.parser").get_text(" ", strip=True))
        result = {"set_code": None, "language": None, "condition": None, "finish": None}
        if not text:
            return result

        # Mercadia descriptions commonly look like:
        #   M10 Lightning Bolt EN SP Normal
        lower_text = text.casefold()
        lower_name = normalize_space(card_name).casefold()
        pos = lower_text.find(lower_name)
        before = normalize_space(text[:pos]) if pos >= 0 else ""
        after = normalize_space(text[pos + len(card_name):]) if pos >= 0 else text
        if before:
            first_token = before.split()[0].strip("-–—")
            if re.fullmatch(r"[A-Za-z0-9]{2,8}", first_token):
                result["set_code"] = first_token.upper()

        tokens = [t.strip(".,;:/()[]") for t in after.split() if t.strip(".,;:/()[]")]
        for token in tokens:
            upper = token.upper()
            if result["language"] is None and upper in self.LANGUAGE_CODES:
                result["language"] = self.LANGUAGE_CODES[upper]
                continue
            if result["condition"] is None and upper in self.CONDITION_CODES:
                result["condition"] = self.CONDITION_CODES[upper]
                continue
            if result["finish"] is None and upper in {"FOIL", "NORMAL", "NON-FOIL", "NONFOIL"}:
                result["finish"] = "Foil" if upper == "FOIL" else "Normal"
        return result

    @staticmethod
    def _collector_from_image(image_url: str | None, set_code: str | None) -> str | None:
        if not image_url:
            return None
        # Common Mercadia media filenames contain `_m10_m10-146-lightning...`.
        if set_code:
            m = re.search(rf"[_/-]{re.escape(set_code)}[-_]([^/_-]+)-", image_url, flags=re.I)
            if m:
                return m.group(1)
        m = re.search(r"[-_](\d+[A-Za-z★]*)-", image_url)
        return m.group(1) if m else None

    def _graphql_request(self, endpoint: str, query: str, variables: dict) -> dict:
        params = {"query": query, "variables": json.dumps(variables, separators=(",", ":"))}
        response = self.http.get(endpoint, params=params, headers={"Accept": "application/json"})
        return response.json()

    def _graphql_search(self, card_name: str) -> list[Listing]:
        last_error = None
        page = 1
        page_size = 50
        out = []
        for endpoint in self.GRAPHQL_ENDPOINTS:
            try:
                page = 1
                out = []
                while page <= 20:
                    variables = {"term": card_name, "page": page, "pageSize": page_size}
                    data = self._graphql_request(endpoint, self.GRAPHQL_QUERY, variables)
                    if data.get("errors"):
                        data = self._graphql_request(endpoint, self.GRAPHQL_QUERY_BASIC, variables)
                    if data.get("errors"):
                        raise RuntimeError(data["errors"][0].get("message", "Mercadia GraphQL error"))
                    products = ((data.get("data") or {}).get("products") or {})
                    items = products.get("items") or []
                    for item in items:
                        name = normalize_space(item.get("name"))
                        if not exactish_card_name(name, card_name):
                            continue
                        if str(item.get("stock_status") or "").upper() != "IN_STOCK":
                            continue
                        stock_raw = item.get("only_x_left_in_stock")
                        stock = as_int(stock_raw) if stock_raw is not None else None
                        if stock is not None and stock <= 0:
                            continue
                        price_node = (((item.get("price_range") or {}).get("minimum_price") or {}).get("final_price") or {})
                        price = price_node.get("value")
                        currency = price_node.get("currency") or "ARS"
                        image = (item.get("small_image") or {}).get("url")
                        meta = self._description_meta((item.get("description") or {}).get("html"), name)
                        collector = self._collector_from_image(image, meta.get("set_code"))
                        product_id = item.get("id")
                        sku = item.get("sku")
                        # The catalog/product/view route is stable even when SEO
                        # URL rewrites differ between Mercadia products.
                        if product_id:
                            url = f"{self.BASE}/index.php/catalog/product/view/id/{product_id}/"
                            if sku:
                                url += f"s/{sku}/"
                        else:
                            key = item.get("url_key") or sku or ""
                            url = f"{self.BASE}/index.php/{key}"
                            if key and not key.endswith(".html"):
                                url += ".html"
                        out.append(Listing(
                            store=self.name,
                            card_name=name,
                            set_name=meta.get("set_code"),
                            set_code=meta.get("set_code"),
                            collector_number=collector,
                            language=meta.get("language"),
                            condition=meta.get("condition"),
                            finish=meta.get("finish"),
                            price=Decimal(str(price)) if price is not None else None,
                            currency=currency,
                            stock=stock,
                            available=True,
                            url=url,
                            image_url=image,
                            product_id=product_id,
                            sku=sku,
                        ))
                    page_info = products.get("page_info") or {}
                    total_pages = as_int(page_info.get("total_pages")) or 1
                    if page >= total_pages or not items:
                        break
                    page += 1
                return out
            except Exception as exc:
                last_error = exc
                continue
        if last_error:
            raise last_error
        return out

    def _autocomplete_links(self, card_name: str):
        """Small public MageWorx endpoint used only if GraphQL is unavailable."""
        data = self.http.get(self.AUTOCOMPLETE, params={"q": card_name}, headers={"Accept": "application/json"}).json()
        candidates = []

        # Different SearchSuite versions wrap the product cards differently.
        for key in ("products", "items", "product"):
            value = data.get(key)
            if isinstance(value, list):
                for item in value:
                    if not isinstance(item, dict):
                        continue
                    name = normalize_space(item.get("name") or item.get("title"))
                    url = item.get("url") or item.get("product_url")
                    if name and url and exactish_card_name(name, card_name):
                        candidates.append((name, urljoin(self.BASE, url)))

        # Some versions return an HTML fragment instead of structured products.
        html = ""
        for key in ("html", "product_html", "content"):
            if isinstance(data.get(key), str):
                html += data[key]
        if html:
            links, _ = self._product_links(html, card_name)
            candidates.extend((name, urljoin(self.BASE, url)) for name, url in links)

        dedup = []
        seen = set()
        for pair in candidates:
            if pair[1] not in seen:
                seen.add(pair[1])
                dedup.append(pair)
        return dedup

    def _legacy_html_search(self, card_name: str) -> list[Listing]:
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
            return [row for row in pool.map(lambda pair: self._detail(*pair), candidates) if row.available and (row.stock is None or row.stock > 0)]

    def search(self, card_name: str) -> list[Listing]:
        graphql_error = None
        try:
            rows = self._graphql_search(card_name)
            if rows:
                return rows
        except Exception as exc:
            graphql_error = exc

        # Try the lightweight public autocomplete before the old catalog page.
        try:
            links = self._autocomplete_links(card_name)
            if links:
                with ThreadPoolExecutor(max_workers=self.DETAIL_WORKERS) as pool:
                    rows = list(pool.map(lambda pair: self._detail(*pair), links))
                rows = [r for r in rows if r.available and (r.stock is None or r.stock > 0)]
                if rows:
                    return rows
        except Exception:
            pass

        try:
            return self._legacy_html_search(card_name)
        except Exception:
            if graphql_error:
                raise graphql_error
            raise
