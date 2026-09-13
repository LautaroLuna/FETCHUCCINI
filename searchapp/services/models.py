from dataclasses import asdict, dataclass
from decimal import Decimal
from typing import Any

from .utils import safe_http_url


@dataclass(slots=True)
class Listing:
    store: str
    card_name: str
    set_name: str | None = None
    set_code: str | None = None
    collector_number: str | None = None
    language: str | None = None
    condition: str | None = None
    finish: str | None = None
    style: str | None = None
    price: Decimal | None = None
    currency: str | None = None
    stock: int | None = None
    available: bool | None = None
    url: str | None = None
    image_url: str | None = None
    product_id: str | int | None = None
    variant_id: str | int | None = None
    sku: str | None = None
    scryfall_id: str | None = None
    raw: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        if self.price is not None:
            data["price"] = str(self.price)
        # Only http(s) destinations are ever exposed to the browser. This is a
        # defense-in-depth check on top of adapter/listing normalization.
        data["url"] = safe_http_url(data.get("url"))
        data["image_url"] = safe_http_url(data.get("image_url"))
        # Raw is useful while developing adapters, but not sent to the browser.
        data.pop("raw", None)
        return data
