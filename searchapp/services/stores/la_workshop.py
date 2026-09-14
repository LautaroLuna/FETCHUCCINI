import requests
from decimal import Decimal
from .base import StoreAdapter
from ..models import Listing
from ..utils import as_int, exactish_card_name


class LaWorkshopAdapter(StoreAdapter):
    key = "la_workshop"
    name = "La Workshop"
    API = "https://la-workshop-tcg.onrender.com/api/search/products"
    BASE = "https://laworkshoptcg.com"

    def search(self, card_name: str) -> list[Listing]:
        out: list[Listing] = []
        page = 1
        while page <= 25:
            try:
                data = self.http.get(self.API, params={
                    "name": card_name,
                    "page": page,
                    "per_page": 20,
                }).json()
            except requests.RequestException as exc:
                if out:
                    self.mark_partial(exc)
                    break
                raise
            products = data.get("products") or data.get("results") or []
            for product in products:
                name = product.get("name") or product.get("card_name") or card_name
                if not exactish_card_name(name, card_name):
                    continue
                set_name = product.get("edition") or product.get("edition_name") or product.get("set_name")
                set_code = product.get("edition_code") or product.get("set_code")
                collector = product.get("collector_number")
                scryfall_id = product.get("scryfall_id")
                image = product.get("image_url") or product.get("image")
                card_definition_id = product.get("id") or product.get("card_definition_id")
                for item in product.get("listings") or []:
                    listing_id = item.get("id") or item.get("listing_id")
                    stock = as_int(item.get("stock") if "stock" in item else item.get("quantity"))
                    price = item.get("current_price") if "current_price" in item else item.get("price")
                    finish = item.get("finish") or item.get("type") or item.get("foil_type")
                    out.append(Listing(
                        store=self.name,
                        card_name=name,
                        set_name=set_name,
                        set_code=set_code,
                        collector_number=str(collector) if collector is not None else None,
                        language=item.get("language"),
                        condition=item.get("condition"),
                        finish=finish,
                        price=Decimal(str(price)) if price is not None else None,
                        currency="USD",
                        stock=stock,
                        available=(stock or 0) > 0,
                        url=f"{self.BASE}/card/{listing_id}" if listing_id else None,
                        image_url=image,
                        product_id=card_definition_id,
                        variant_id=listing_id,
                        scryfall_id=scryfall_id,
                    ))
            pages = as_int(data.get("pages")) or 1
            if page >= pages:
                break
            page += 1
        return out
