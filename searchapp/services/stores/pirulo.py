import re
from decimal import Decimal
from urllib.parse import urljoin
from .base import StoreAdapter
from ..models import Listing
from ..utils import as_int, exactish_card_name, first


class PiruloAdapter(StoreAdapter):
    key = "pirulo"
    name = "Pirulo"
    BASE = "https://mtgpirulo.com"
    SEARCH = "https://lgsc-search.lgs-companion.com/suggest-name"
    STORE_HASH = "8lxt5ysjan"
    # The storefront itself uses 12 for this suggestions endpoint. Higher values
    # are rejected with HTTP 400, so keep this aligned with the public frontend.
    SUGGEST_LIMIT = 12

    GQL = """
    query PDPVariants($id:Int!,$first:Int!) {
      site { product(entityId:$id) {
        entityId name
        prices { price { value currencyCode } }
        variants(first:$first) { edges { node {
          entityId sku isPurchasable
          options(first:50) { edges { node { displayName values(first:1) { edges { node { entityId label } } } } } }
          defaultImage { url(width:80) altText }
          inventory { isInStock aggregated { availableToSell } }
          prices { price { value currencyCode } salePrice { value currencyCode } basePrice { value currencyCode } retailPrice { value currencyCode } }
        } } }
      } }
    }
    """

    def _token_from_html(self, html: str) -> str | None:
        patterns = [
            r'bcStoreFrontToken\\?"\s*:\s*\\?"([^"\\]+)',
            r'bcStoreFrontToken["\']?\s*[:=]\s*["\']([^"\']+)',
            r'Authorization["\']?\s*:\s*["\']Bearer\s+([^"\']+)',
        ]
        for pattern in patterns:
            m = re.search(pattern, html)
            if m:
                return m.group(1)
        return None

    def _variant_rows(self, product: dict, search_product: dict, token: str) -> list[Listing]:
        product_id = as_int(product.get("bc_product_id") or product.get("entityId") or product.get("product_id"))
        if not product_id:
            return []
        resp = self.http.post(
            f"{self.BASE}/graphql",
            json={"query": self.GQL, "variables": {"id": product_id, "first": 250}},
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        ).json()
        gql_product = (((resp.get("data") or {}).get("site") or {}).get("product") or {})
        out = []
        for edge in ((gql_product.get("variants") or {}).get("edges") or []):
            node = edge.get("node") or {}
            inv = node.get("inventory") or {}
            ats = ((inv.get("aggregated") or {}).get("availableToSell"))
            stock = as_int(ats)
            if not node.get("isPurchasable") or not inv.get("isInStock") or (stock is not None and stock <= 0):
                continue
            options = {}
            for oedge in ((node.get("options") or {}).get("edges") or []):
                option = oedge.get("node") or {}
                label = first(((option.get("values") or {}).get("edges") or [{}]))
                if isinstance(label, dict):
                    label = (label.get("node") or {}).get("label")
                options[(option.get("displayName") or "").casefold()] = label
            prices = node.get("prices") or {}
            current = ((prices.get("price") or {}).get("value"))
            sale = ((prices.get("salePrice") or {}).get("value"))
            if sale is not None and current is not None and Decimal(str(sale)) < Decimal(str(current)):
                current = sale
            currency = ((prices.get("price") or {}).get("currencyCode")) or "USD"
            out.append(Listing(
                store=self.name,
                card_name=search_product.get("card_name") or search_product.get("name") or gql_product.get("name"),
                set_name=search_product.get("set_name"),
                collector_number=str(search_product.get("card_number")) if search_product.get("card_number") is not None else None,
                language=options.get("language"),
                condition=options.get("condition"),
                finish=options.get("finish") or search_product.get("finish"),
                price=Decimal(str(current)) if current is not None else None,
                currency=currency,
                stock=stock,
                available=True,
                url=urljoin(self.BASE, search_product.get("product_url") or search_product.get("url") or ""),
                image_url=search_product.get("image_url") or ((node.get("defaultImage") or {}).get("url")),
                product_id=product_id,
                variant_id=node.get("entityId"),
                sku=node.get("sku"),
            ))
        return out

    def search(self, card_name: str) -> list[Listing]:
        data = self.http.get(
            self.SEARCH,
            params={
                "store_hash": self.STORE_HASH,
                "q": card_name,
                "limit": self.SUGGEST_LIMIT,
                "visible_only": "true",
                "currency_code": "USD",
            },
            headers={"Accept": "application/json"},
        ).json()

        out = []
        for product in data.get("products") or []:
            candidate = product.get("card_name") or product.get("name")
            if not exactish_card_name(candidate, card_name):
                continue
            url = urljoin(self.BASE, product.get("product_url") or product.get("url") or "")
            try:
                html = self.http.get(url).text
                token = self._token_from_html(html)
                if token:
                    rows = self._variant_rows(product, product, token)
                    if rows:
                        out.extend(rows)
                        continue
            except Exception:
                # The search result still contains useful aggregate data, so a
                # product-page/GraphQL failure should not discard the listing.
                pass

            stock = as_int(product.get("available_qty") or product.get("inventory_level"))
            price = product.get("display_price") or product.get("calculated_price") or product.get("price")
            out.append(Listing(
                store=self.name,
                card_name=candidate or card_name,
                set_name=product.get("set_name"),
                collector_number=str(product.get("card_number")) if product.get("card_number") is not None else None,
                finish=product.get("finish"),
                price=Decimal(str(price)) if price is not None else None,
                currency="USD",
                stock=stock,
                available=bool(product.get("is_in_stock") or product.get("in_stock")),
                url=url,
                image_url=product.get("image_url"),
                product_id=product.get("bc_product_id") or product.get("product_id"),
                sku=product.get("sku"),
            ))
        return out
