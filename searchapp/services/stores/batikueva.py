import re
from decimal import Decimal
from urllib.parse import urljoin
from bs4 import BeautifulSoup
from .base import StoreAdapter
from ..models import Listing
from ..utils import as_int, exactish_card_name, json_attr, normalize_space


class BatikuevaAdapter(StoreAdapter):
    key = "batikueva"
    name = "La Batikueva"
    BASE = "https://www.labatikuevastore.com"
    PAGE_SIZE = 12

    def _card_container(self, node):
        current = node
        for _ in range(6):
            if not current:
                break
            if current.find("a", href=re.compile(r"/productos/")):
                return current
            current = current.parent
        return node.parent

    def _product_meta(self, container):
        link = container.find("a", href=re.compile(r"/productos/")) if container else None
        title = None
        if link:
            title = normalize_space(link.get("title") or link.get_text(" ", strip=True))
        image = None
        img = container.find("img") if container else None
        if img:
            image = img.get("data-srcset") or img.get("data-src") or img.get("src")
            if image and "," in image:
                image = image.split(",")[0].split()[0]
            if image and image.startswith("//"):
                image = "https:" + image
        product_id = None
        if container:
            pnode = container.find(attrs={"data-product-id": True})
            if pnode:
                product_id = pnode.get("data-product-id")
        return title, (link.get("href") if link else None), image, product_id

    def _detail_set(self, url: str):
        try:
            soup = BeautifulSoup(self.http.get(url).text, "html.parser")
        except Exception:
            return None, None
        breadcrumbs = [normalize_space(a.get_text(" ", strip=True)) for a in soup.select(".breadcrumb a, .breadcrumbs a")]
        set_name = None
        for text in reversed(breadcrumbs):
            low = text.casefold()
            if text and "lightning bolt" not in low and text not in {"Inicio", "Home", "Singles"}:
                set_name = text
                break
        collector = None
        img = soup.select_one("meta[property='og:image'], img[src*='lightning']")
        src = img.get("content") if img and img.name == "meta" else (img.get("src") if img else None)
        if src:
            m = re.search(r"lightningbolt[^0-9]*(\d{2,4})", src, flags=re.I)
            if m:
                collector = m.group(1)
        return set_name, collector

    def _fetch_page(self, card_name: str, page: int):
        """Return (html, explicit_has_next_or_none).

        Tiendanube's hybrid-scroll endpoint normally returns JSON, but on some
        requests it answers with regular HTML instead. Treat both forms as valid
        so a harmless content-type/transport change does not break the adapter.
        """
        if page == 1:
            response = self.http.get(
                f"{self.BASE}/search/",
                params={"q": card_name},
                headers={"Accept": "text/html,application/xhtml+xml"},
            )
            return response.text, None

        response = self.http.get(
            f"{self.BASE}/search/page/{page}/",
            params={
                "q": card_name,
                "results_only": "true",
                "limit": self.PAGE_SIZE,
                "theme": "amazonas",
            },
            headers={
                "Accept": "application/json, text/javascript, */*; q=0.01",
                "X-Requested-With": "XMLHttpRequest",
                "Referer": f"{self.BASE}/search/?q={card_name.replace(' ', '+')}",
            },
        )

        try:
            data = response.json()
        except ValueError:
            # Some Tiendanube responses arrive as full/partial HTML rather than
            # JSON. Parsing that HTML is enough because data-variants is embedded.
            return response.text, None

        if isinstance(data, dict):
            return data.get("html") or "", data.get("has_next")
        return response.text, None

    def search(self, card_name: str) -> list[Listing]:
        out = []
        seen_products = set()

        for page in range(1, 51):
            html, explicit_has_next = self._fetch_page(card_name, page)
            soup = BeautifulSoup(html or "", "html.parser")
            nodes = soup.find_all(attrs={"data-variants": True})
            if not nodes:
                break

            page_product_ids = set()
            page_added_any_product = False

            for node in nodes:
                variants = json_attr(node.get("data-variants")) or []
                container = self._card_container(node)
                title, href, image, product_id = self._product_meta(container)

                stable_id = str(product_id or href or title or "")
                if stable_id:
                    page_product_ids.add(stable_id)
                    if stable_id not in seen_products:
                        page_added_any_product = True
                        seen_products.add(stable_id)

                if not exactish_card_name(title, card_name):
                    continue

                url = urljoin(self.BASE, href or "")
                # Production-friendly mode: all comparison-critical fields already
                # live in the search card. Avoid one extra product-page request per
                # result, which made public searches much slower.
                set_name, collector = None, None
                style = None
                m = re.search(r"\(([^)]+)\)", title or "")
                if m:
                    style = m.group(1)
                title_low = (title or "").casefold()
                finish = "Foil Etched" if "foil etched" in title_low else ("Foil" if "foil" in title_low else None)

                for variant in variants:
                    stock = as_int(variant.get("stock"))
                    price = variant.get("price_number")
                    out.append(Listing(
                        store=self.name,
                        card_name=card_name,
                        set_name=set_name,
                        collector_number=collector,
                        language=variant.get("option1"),
                        condition=variant.get("option2"),
                        finish=finish,
                        style=style,
                        price=Decimal(str(price)) if price is not None else None,
                        currency="ARS",
                        stock=stock,
                        available=bool(variant.get("available")) and (stock is None or stock > 0),
                        url=url,
                        image_url=image,
                        product_id=product_id,
                        variant_id=variant.get("id"),
                    ))

            # Prefer the API's own pagination signal when it is available.
            if explicit_has_next is False:
                break

            # HTML fallback has no has_next field. A repeated page means the
            # endpoint redirected/fell back, so stop instead of looping 50 times.
            if page > 1 and not page_added_any_product:
                break

            # Fewer than a full page strongly indicates the final page.
            if explicit_has_next is None and len(page_product_ids) < self.PAGE_SIZE:
                break

        return out
