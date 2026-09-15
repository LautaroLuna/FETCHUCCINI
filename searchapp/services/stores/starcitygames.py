from decimal import Decimal
from urllib.parse import urljoin
from .base import StoreAdapter
from ..models import Listing
from ..utils import as_int, exactish_card_name, first


class StarCityGamesAdapter(StoreAdapter):
    key = "starcitygames"
    name = "StarCityGames"
    API = "https://ajax.starcitygames.com/hawksearch/searchapi/api/v2/search"
    BASE = "https://starcitygames.com"

    def _payload(self, card_name: str, page: int = 1) -> dict:
        return {
            "Keyword": card_name,
            "FacetSelections": {},
            "MaxPerPage": 96,
            "PageNo": page,
            "Variant": {"MaxPerPage": 32},
        }

    def search(self, card_name: str) -> list[Listing]:
        out: list[Listing] = []
        page = 1
        while page <= 10:
            data = self.http.post(self.API, json=self._payload(card_name, page)).json()
            for result in data.get("Results") or []:
                doc = result.get("Document") or {}
                name = first(doc.get("card_name")) or first(doc.get("item_display_name")) or card_name
                if not exactish_card_name(name, card_name):
                    continue
                set_name = first(doc.get("set")) or first(doc.get("filter_set"))
                collector = first(doc.get("collector_number"))
                finish = first(doc.get("mtg_finish")) or first(doc.get("finish"))
                style = first(doc.get("card_styles_combined")) or first(doc.get("card_styles"))
                image = first(doc.get("image"))
                parent_url = first(doc.get("url_detail"))
                parent_product_id = first(doc.get("unique_id"))
                children = doc.get("hawk_child_attributes") or []
                for child in children:
                    price = first(child.get("calculated_price")) or first(child.get("price"))
                    sale = first(child.get("price_sale"))
                    if sale not in (None, "", "0", "0.00"):
                        price = sale
                    stock = as_int(first(child.get("qty")))
                    purchasing_disabled = bool(first(child.get("purchasing_disabled"), False))
                    in_stock = str(first(child.get("variant_instockonly"), "")).lower() == "yes"
                    out.append(Listing(
                        store=self.name,
                        card_name=name,
                        set_name=set_name,
                        collector_number=str(collector) if collector is not None else None,
                        language=first(child.get("variant_language")) or first(doc.get("language")),
                        condition=first(child.get("condition")),
                        finish=finish,
                        style=style,
                        price=Decimal(str(price)) if price is not None else None,
                        currency="USD",
                        stock=stock,
                        available=(stock or 0) > 0 and in_stock and not purchasing_disabled,
                        url=urljoin(self.BASE, first(child.get("url")) or parent_url or ""),
                        image_url=image,
                        product_id=first(child.get("prod_id")) or parent_product_id,
                        variant_id=first(child.get("var_id")),
                        sku=first(child.get("variant_sku")),
                    ))
            pagination = data.get("Pagination") or {}
            pages = as_int(pagination.get("NofPages")) or 1
            if page >= pages:
                break
            page += 1
        return out
