import re
import time
from decimal import Decimal
from urllib.parse import urljoin

import requests

from .base import StoreAdapter
from ..models import Listing
from ..utils import as_int, exactish_card_name, first, normalize_space


class PiruloAdapter(StoreAdapter):
    key = "pirulo"
    name = "Pirulo"
    BASE = "https://mtgpirulo.com"
    SEARCH = "https://lgsc-search.lgs-companion.com/suggest-name"
    STORE_HASH = "8lxt5ysjan"
    SUGGEST_LIMIT = 12
    TOKEN_TTL_SECONDS = 20 * 60
    _cached_storefront_token = None
    _cached_storefront_token_until = 0.0

    # v0.23: The LGS Companion suggestion host rejects some datacenter IPs.
    # BigCommerce's own Storefront GraphQL API is also a public storefront data
    # source and can perform the product search directly. We dynamically read
    # the storefront token from Pirulo's own HTML instead of hardcoding it.
    SEARCH_GQL = """
    query SearchProducts($term:String!,$first:Int!,$variantFirst:Int!) {
      site {
        search {
          searchProducts(filters:{searchTerm:$term}) {
            products(first:$first) {
              edges { node {
                entityId
                name
                path
                sku
                defaultImage { url(width:300) altText }
                prices { price { value currencyCode } }
                inventory { isInStock aggregated { availableToSell } }
                variants(first:$variantFirst) { edges { node {
                  entityId sku isPurchasable
                  options(first:50) { edges { node {
                    displayName
                    values(first:1) { edges { node { entityId label } } }
                  } } }
                  defaultImage { url(width:300) altText }
                  inventory { isInStock aggregated { availableToSell } }
                  prices {
                    price { value currencyCode }
                    salePrice { value currencyCode }
                    basePrice { value currencyCode }
                    retailPrice { value currencyCode }
                  }
                } } }
              } }
            }
          }
        }
      }
    }
    """

    PDP_GQL = """
    query PDPVariants($id:Int!,$first:Int!) {
      site { product(entityId:$id) {
        entityId name path sku
        prices { price { value currencyCode } }
        variants(first:$first) { edges { node {
          entityId sku isPurchasable
          options(first:50) { edges { node { displayName values(first:1) { edges { node { entityId label } } } } } }
          defaultImage { url(width:300) altText }
          inventory { isInStock aggregated { availableToSell } }
          prices { price { value currencyCode } salePrice { value currencyCode } basePrice { value currencyCode } retailPrice { value currencyCode } }
        } } }
      } }
    }
    """

    STYLE_TERMS = {
        "borderless", "showcase", "full art", "extended art", "retro frame",
        "etched", "serialized", "surge foil", "galaxy foil",
    }

    def _token_from_html(self, html: str) -> str | None:
        patterns = [
            r"(?:STOREFRONT_TOKEN|STOREFRONT_API_TOKEN)\s*=\s*['\"]([^'\"]+)",
            r'bcStoreFrontToken\\?"\s*:\s*\\?"([^"\\]+)',
            r'bcStoreFrontToken["\']?\s*[:=]\s*["\']([^"\']+)',
            r'Authorization["\']?\s*:\s*["\']Bearer\s+([^"\']+)',
        ]
        for pattern in patterns:
            m = re.search(pattern, html, flags=re.I)
            if m:
                return m.group(1)
        return None

    @classmethod
    def _invalidate_storefront_token(cls):
        cls._cached_storefront_token = None
        cls._cached_storefront_token_until = 0.0

    def _storefront_token(self, force_refresh: bool = False) -> str | None:
        # The token is intentionally fetched at runtime from public storefront
        # HTML. Cache it only in process memory to avoid an extra Pirulo page
        # request for every card search. It is never written to disk/source.
        now = time.monotonic()
        cls = type(self)
        if (
            not force_refresh
            and cls._cached_storefront_token
            and now < cls._cached_storefront_token_until
        ):
            return cls._cached_storefront_token

        if force_refresh:
            cls._invalidate_storefront_token()

        for url in (self.BASE + "/", self.BASE + "/magic-the-gathering/mtg-singles/"):
            try:
                token = self._token_from_html(self.http.get(url).text)
                if token:
                    cls._cached_storefront_token = token
                    cls._cached_storefront_token_until = time.monotonic() + self.TOKEN_TTL_SECONDS
                    return token
            except requests.RequestException:
                continue
        return None

    def _title_meta(self, title: str, query: str) -> dict:
        """Extract useful MTG metadata from Pirulo's BigCommerce product name.

        Examples:
          Lightning Bolt (A25) (#141)
          Lightning Bolt (SLD) (Foil) (Full Art) (#83)
        """
        clean = normalize_space(title)
        groups = [normalize_space(x) for x in re.findall(r"\(([^()]*)\)", clean)]
        base = normalize_space(re.sub(r"\s*\([^()]*\)\s*", " ", clean))
        # For transform/adventure names, keep the full visible name. For normal
        # products, the base text is the card name.
        card_name = base or query
        set_code = None
        collector = None
        finish = None
        styles = []
        for group in groups:
            lower = group.casefold()
            if group.startswith("#"):
                collector = group[1:].strip() or None
            elif lower in {"foil", "non-foil", "nonfoil"} or "foil" in lower:
                finish = group
            elif lower in self.STYLE_TERMS or any(term in lower for term in self.STYLE_TERMS):
                styles.append(group)
            elif set_code is None and re.fullmatch(r"[A-Za-z0-9]{2,8}", group):
                set_code = group.upper()
        return {
            "card_name": card_name,
            "set_code": set_code,
            "set_name": set_code,
            "collector_number": collector,
            "finish": finish,
            "style": " · ".join(styles) if styles else None,
        }

    @staticmethod
    def _option_map(node: dict) -> dict[str, str | None]:
        options = {}
        for oedge in ((node.get("options") or {}).get("edges") or []):
            option = oedge.get("node") or {}
            label = first(((option.get("values") or {}).get("edges") or [{}]))
            if isinstance(label, dict):
                label = (label.get("node") or {}).get("label")
            options[(option.get("displayName") or "").casefold()] = label
        return options

    def _listing_from_variant(self, product: dict, variant: dict, query: str) -> Listing | None:
        inventory = variant.get("inventory") or {}
        stock = as_int(((inventory.get("aggregated") or {}).get("availableToSell")))
        in_stock = inventory.get("isInStock")
        if not variant.get("isPurchasable") or in_stock is False or (stock is not None and stock <= 0):
            return None

        title = product.get("name") or query
        meta = self._title_meta(title, query)
        if not exactish_card_name(meta["card_name"], query):
            return None

        options = self._option_map(variant)
        prices = variant.get("prices") or {}
        price_node = prices.get("price") or {}
        current = price_node.get("value")
        sale = (prices.get("salePrice") or {}).get("value")
        if sale is not None and current is not None and Decimal(str(sale)) < Decimal(str(current)):
            current = sale
        currency = price_node.get("currencyCode") or "USD"
        path = product.get("path") or ""
        image = (variant.get("defaultImage") or {}).get("url") or (product.get("defaultImage") or {}).get("url")

        return Listing(
            store=self.name,
            card_name=meta["card_name"],
            set_name=meta["set_name"],
            set_code=meta["set_code"],
            collector_number=meta["collector_number"],
            language=options.get("language"),
            condition=options.get("condition"),
            finish=options.get("finish") or meta["finish"],
            style=meta["style"],
            price=Decimal(str(current)) if current is not None else None,
            currency=currency,
            stock=stock,
            available=True,
            url=urljoin(self.BASE, path),
            image_url=image,
            product_id=product.get("entityId"),
            variant_id=variant.get("entityId"),
            sku=variant.get("sku") or product.get("sku"),
        )

    def _graphql_search(self, card_name: str) -> list[Listing]:
        token = self._storefront_token()
        if not token:
            raise RuntimeError("Pirulo: no se pudo obtener el token público de Storefront.")

        def request_graphql(active_token: str):
            return self.http.post(
                f"{self.BASE}/graphql",
                json={
                    "query": self.SEARCH_GQL,
                    "variables": {"term": card_name, "first": 50, "variantFirst": 250},
                },
                headers={
                    "Accept": "application/json",
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {active_token}",
                },
            ).json()

        try:
            response = request_graphql(token)
        except requests.HTTPError as exc:
            status = getattr(getattr(exc, "response", None), "status_code", None)
            if status not in {401, 403}:
                raise
            token = self._storefront_token(force_refresh=True)
            if not token:
                raise
            response = request_graphql(token)
        if response.get("errors"):
            raise RuntimeError(f"Pirulo GraphQL: {response['errors'][0].get('message', 'error')}")
        products = (((((response.get("data") or {}).get("site") or {}).get("search") or {}).get("searchProducts") or {}).get("products") or {}).get("edges") or []
        out = []
        for edge in products:
            product = edge.get("node") or {}
            meta = self._title_meta(product.get("name") or "", card_name)
            if not exactish_card_name(meta["card_name"], card_name):
                continue
            variants = ((product.get("variants") or {}).get("edges") or [])
            if variants:
                for vedge in variants:
                    listing = self._listing_from_variant(product, vedge.get("node") or {}, card_name)
                    if listing:
                        out.append(listing)
                continue

            # Rare fallback for a product without variants.
            inv = product.get("inventory") or {}
            stock = as_int(((inv.get("aggregated") or {}).get("availableToSell")))
            if inv.get("isInStock") is False or (stock is not None and stock <= 0):
                continue
            p = (product.get("prices") or {}).get("price") or {}
            value = p.get("value")
            out.append(Listing(
                store=self.name,
                card_name=meta["card_name"], set_name=meta["set_name"], set_code=meta["set_code"],
                collector_number=meta["collector_number"], finish=meta["finish"], style=meta["style"],
                price=Decimal(str(value)) if value is not None else None,
                currency=p.get("currencyCode") or "USD", stock=stock, available=True,
                url=urljoin(self.BASE, product.get("path") or ""),
                image_url=(product.get("defaultImage") or {}).get("url"),
                product_id=product.get("entityId"), sku=product.get("sku"),
            ))
        return out

    def _suggest_search(self, card_name: str) -> list[Listing]:
        """Legacy public suggest endpoint; retained only as a fallback."""
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
        token = None
        for product in data.get("products") or []:
            candidate = product.get("card_name") or product.get("name")
            if not exactish_card_name(candidate, card_name):
                continue
            url = urljoin(self.BASE, product.get("product_url") or product.get("url") or "")
            try:
                html = self.http.get(url).text
                token = token or self._token_from_html(html)
                if token:
                    product_id = as_int(product.get("bc_product_id") or product.get("entityId") or product.get("product_id"))
                    if product_id:
                        resp = self.http.post(
                            f"{self.BASE}/graphql",
                            json={"query": self.PDP_GQL, "variables": {"id": product_id, "first": 250}},
                            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
                        ).json()
                        gql_product = (((resp.get("data") or {}).get("site") or {}).get("product") or {})
                        gql_product.setdefault("path", product.get("product_url") or product.get("url"))
                        gql_product.setdefault("defaultImage", {"url": product.get("image_url")})
                        rows = []
                        for edge in ((gql_product.get("variants") or {}).get("edges") or []):
                            listing = self._listing_from_variant(gql_product, edge.get("node") or {}, card_name)
                            if listing:
                                rows.append(listing)
                        if rows:
                            out.extend(rows)
                            continue
            except Exception:
                pass

            stock = as_int(product.get("available_qty") or product.get("inventory_level"))
            available = bool(product.get("is_in_stock") or product.get("in_stock"))
            if not available or (stock is not None and stock <= 0):
                continue
            price = product.get("display_price") or product.get("calculated_price") or product.get("price")
            meta = self._title_meta(candidate or card_name, card_name)
            out.append(Listing(
                store=self.name, card_name=meta["card_name"], set_name=product.get("set_name") or meta["set_name"],
                set_code=meta["set_code"], collector_number=str(product.get("card_number") or meta["collector_number"] or "") or None,
                finish=product.get("finish") or meta["finish"], style=meta["style"],
                price=Decimal(str(price)) if price is not None else None, currency="USD", stock=stock, available=True,
                url=url, image_url=product.get("image_url"), product_id=product.get("bc_product_id") or product.get("product_id"), sku=product.get("sku"),
            ))
        return out

    def search(self, card_name: str) -> list[Listing]:
        # BigCommerce Storefront is the authoritative online path. An empty
        # list is a perfectly valid result (the card may simply have no stock).
        # Previously we treated [] as a reason to fall back to LGS Companion;
        # Railway is blocked by that host, so many legitimate zero-result
        # searches were incorrectly shown as "Pirulo: no disponible online".
        try:
            return self._graphql_search(card_name)
        except Exception as graphql_error:
            # Only use the legacy suggestion service when GraphQL itself
            # actually failed. Do NOT use it just because GraphQL found 0 rows.
            try:
                return self._suggest_search(card_name)
            except Exception:
                raise graphql_error
