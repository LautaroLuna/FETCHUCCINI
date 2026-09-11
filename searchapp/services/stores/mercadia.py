import json
import re
from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

from .base import StoreAdapter
from ..models import Listing
from ..utils import as_int, exactish_card_name, normalize_space, parse_ars


class MercadiaAdapter(StoreAdapter):
    key = "mercadia"
    name = "Mercadia"
    BASE = "https://mercadiacity.com"
    SEARCH = f"{BASE}/index.php/catalogsearch/result/"
    GRAPHQL_ENDPOINTS = (f"{BASE}/graphql", f"{BASE}/index.php/graphql")
    AUTOCOMPLETE = f"{BASE}/index.php/mageworx_searchsuiteautocomplete/ajax/index/"
    NATIVE_SUGGEST = f"{BASE}/index.php/search/ajax/suggest/"
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
            matches = re.findall(rf"[_/-]{re.escape(set_code)}[-_]([^/_-]+)-", image_url, flags=re.I)
            for value in reversed(matches):
                if re.fullmatch(r"\d+[A-Za-z★]*", value):
                    return value
        matches = re.findall(r"[-_](\d+[A-Za-z★]*)-", image_url)
        return matches[-1] if matches else None

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

    @staticmethod
    def _flatten_autocomplete_products(data: dict) -> list[dict]:
        """Return MageWorx product entries from its public autocomplete JSON.

        Current MageWorx versions return {"result": [{"code": "product",
        "data": [...]}, ...]}. Older/customized versions sometimes wrap the
        same payload differently, so this deliberately accepts a few shapes.
        """
        products = []

        def add_items(value):
            if isinstance(value, list):
                for item in value:
                    if isinstance(item, dict):
                        products.append(item)

        result = data.get("result") if isinstance(data, dict) else None
        if isinstance(result, list):
            for section in result:
                if not isinstance(section, dict):
                    continue
                code = str(section.get("code") or "").casefold()
                payload = section.get("data")
                if "product" in code and isinstance(payload, list):
                    add_items(payload)

        # Compatibility with stores that expose products directly.
        if not products and isinstance(data, dict):
            for key in ("products", "items", "product"):
                add_items(data.get(key))

        return products

    @staticmethod
    def _field(item: dict, *names):
        for name in names:
            if name in item and item.get(name) not in (None, ""):
                return item.get(name)
        return None

    def _listing_from_autocomplete_item(self, item: dict, card_name: str, salable_signal_available: bool) -> Listing | None:
        name = normalize_space(self._field(item, "name", "title", "product_name"))
        if not name or not exactish_card_name(name, card_name):
            return None

        # MageWorx only adds add_to_cart for salable items. If the field is
        # enabled in this store's autocomplete config, its absence is a reliable
        # out-of-stock signal and we skip the item entirely.
        if salable_signal_available and not self._field(item, "add_to_cart", "addToCart", "addtocart"):
            return None

        url = self._field(item, "url", "product_url", "productUrl")
        if not url:
            return None
        url = urljoin(self.BASE, str(url))

        image = self._field(item, "image", "image_url", "small_image", "thumbnail")
        if isinstance(image, dict):
            image = image.get("url") or image.get("src")
        if image:
            image = urljoin(self.BASE, str(image))

        sku = normalize_space(str(self._field(item, "sku") or "")) or None
        description = self._field(item, "description", "short_description", "shortDescription")
        if isinstance(description, dict):
            description = description.get("html") or description.get("value") or ""
        description = str(description or "")
        meta = self._description_meta(description, name)

        price_raw = self._field(item, "price", "final_price", "finalPrice")
        if isinstance(price_raw, dict):
            price_raw = price_raw.get("value") or price_raw.get("amount") or price_raw.get("formatted")
        if isinstance(price_raw, (int, float, Decimal)):
            price = Decimal(str(price_raw))
        else:
            price_text = BeautifulSoup(str(price_raw or ""), "html.parser").get_text(" ", strip=True)
            price = parse_ars(price_text)

        collector = self._collector_from_image(image, meta.get("set_code"))
        product_id = None
        for pattern in (r"/id/(\d+)/", r"product/(\d+)", r"product_id[=/](\d+)"):
            m = re.search(pattern, url)
            if m:
                product_id = m.group(1)
                break

        return Listing(
            store=self.name,
            card_name=name,
            set_name=meta.get("set_code"),
            set_code=meta.get("set_code"),
            collector_number=collector,
            language=meta.get("language"),
            condition=meta.get("condition"),
            finish=meta.get("finish"),
            price=price,
            currency="ARS",
            stock=None,
            available=True,
            url=url,
            image_url=image,
            product_id=product_id,
            sku=sku,
        )

    def _autocomplete_listings(self, card_name: str) -> list[Listing]:
        """Use MageWorx autocomplete as a self-contained data source.

        This intentionally does *not* open the product detail pages. Mercadia's
        WAF may reject those requests from hosting providers even when the small
        public autocomplete endpoint is allowed.
        """
        response = self.http.get(
            self.AUTOCOMPLETE,
            params={"q": card_name},
            headers={"Accept": "application/json, text/javascript, */*; q=0.01"},
        )
        data = response.json()
        items = self._flatten_autocomplete_products(data)
        if not items:
            return []

        salable_signal_available = any(
            any(key in item for key in ("add_to_cart", "addToCart", "addtocart"))
            for item in items
            if isinstance(item, dict)
        )

        out = []
        seen = set()
        for item in items:
            if not isinstance(item, dict):
                continue
            listing = self._listing_from_autocomplete_item(item, card_name, salable_signal_available)
            if not listing:
                continue
            key = (listing.url, listing.sku)
            if key in seen:
                continue
            seen.add(key)
            out.append(listing)
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
        errors = []

        # First choice: MageWorx autocomplete already contains product name,
        # SKU, image, description, price and URL. Using it directly avoids the
        # detail-page requests that Mercadia blocks most aggressively on hosts.
        try:
            rows = self._autocomplete_listings(card_name)
            if rows:
                return rows
        except Exception as exc:
            errors.append(f"autocomplete: {exc}")

        # Second choice: Magento storefront GraphQL.
        try:
            rows = self._graphql_search(card_name)
            if rows:
                return rows
        except Exception as exc:
            errors.append(f"graphql: {exc}")

        # Older MageWorx path: URLs from autocomplete + detail enrichment. This
        # remains useful locally even if hosted detail requests are rejected.
        try:
            links = self._autocomplete_links(card_name)
            if links:
                with ThreadPoolExecutor(max_workers=self.DETAIL_WORKERS) as pool:
                    rows = list(pool.map(lambda pair: self._detail(*pair), links))
                rows = [r for r in rows if r.available and (r.stock is None or r.stock > 0)]
                if rows:
                    return rows
        except Exception as exc:
            errors.append(f"autocomplete-detail: {exc}")

        try:
            rows = self._legacy_html_search(card_name)
            if rows:
                return rows
        except Exception as exc:
            errors.append(f"catalogsearch: {exc}")

        # Keep the full chain in the server/UI tooltip. That lets us know which
        # public Mercadia path is rejecting Railway without needing screenshots.
        if errors:
            raise RuntimeError("Mercadia routes failed | " + " | ".join(errors))
        return []

