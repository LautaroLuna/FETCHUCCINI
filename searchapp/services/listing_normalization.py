from __future__ import annotations

from dataclasses import replace
from typing import Iterable

from .models import Listing
from .utils import normalize_card_search_text, normalize_space, safe_http_url


_LANGUAGE_ALIASES = {
    "en": "Inglés",
    "eng": "Inglés",
    "english": "Inglés",
    "ingles": "Inglés",
    "es": "Español",
    "sp": "Español",
    "spa": "Español",
    "spanish": "Español",
    "espanol": "Español",
    "pt": "Portugués",
    "por": "Portugués",
    "portuguese": "Portugués",
    "portugues": "Portugués",
    "fr": "Francés",
    "fre": "Francés",
    "fra": "Francés",
    "french": "Francés",
    "frances": "Francés",
    "de": "Alemán",
    "ger": "Alemán",
    "deu": "Alemán",
    "german": "Alemán",
    "aleman": "Alemán",
    "it": "Italiano",
    "ita": "Italiano",
    "italian": "Italiano",
    "italiano": "Italiano",
    "ja": "Japonés",
    "jp": "Japonés",
    "jpn": "Japonés",
    "japanese": "Japonés",
    "japones": "Japonés",
    "ko": "Coreano",
    "kor": "Coreano",
    "korean": "Coreano",
    "coreano": "Coreano",
    "ru": "Ruso",
    "rus": "Ruso",
    "russian": "Ruso",
    "ruso": "Ruso",
    "zhs": "Chino simplificado",
    "zh-cn": "Chino simplificado",
    "zh cn": "Chino simplificado",
    "simplified chinese": "Chino simplificado",
    "chino simplificado": "Chino simplificado",
    "zht": "Chino tradicional",
    "zh-tw": "Chino tradicional",
    "zh tw": "Chino tradicional",
    "traditional chinese": "Chino tradicional",
    "chino tradicional": "Chino tradicional",
}

_CONDITION_ALIASES = {
    "nm": "Near Mint",
    "near mint": "Near Mint",
    "mint": "Near Mint",
    "lp": "Lightly Played",
    "lightly played": "Lightly Played",
    "levemente jugada": "Lightly Played",
    "ligeramente jugada": "Lightly Played",
    "poco jugada": "Lightly Played",
    "mp": "Moderately Played",
    "moderately played": "Moderately Played",
    "moderadamente jugada": "Moderately Played",
    "sp": "Played",
    "played": "Played",
    "slightly played": "Played",
    "jugada": "Played",
    "jugada sp": "Played",
    "hp": "Heavily Played",
    "heavily played": "Heavily Played",
    "muy jugada": "Heavily Played",
    "muy usada": "Heavily Played",
    "damaged": "Damaged",
    "dmg": "Damaged",
    "poor": "Damaged",
    "danada": "Damaged",
    "danado": "Damaged",
    "ex": "Excelente",
    "ex nm": "Excelente",
    "excelente": "Excelente",
}

_FINISH_ALIASES = {
    "normal": "Non-foil",
    "regular": "Non-foil",
    "non foil": "Non-foil",
    "nonfoil": "Non-foil",
    "non-foil": "Non-foil",
    "foil": "Foil",
    "etched": "Foil Etched",
    "foil etched": "Foil Etched",
    "etched foil": "Foil Etched",
}


def _lookup_key(value: str | None) -> str:
    return normalize_card_search_text(value).replace(" // ", " ")


def normalize_language(value: str | None) -> str | None:
    text = normalize_space(value)
    if not text:
        return None
    return _LANGUAGE_ALIASES.get(_lookup_key(text), text)


def normalize_condition(value: str | None) -> str | None:
    text = normalize_space(value)
    if not text:
        return None
    key = _lookup_key(text)
    if key in _CONDITION_ALIASES:
        return _CONDITION_ALIASES[key]
    # Common storefronts append explanatory text after the grade.
    for prefix, canonical in (
        ("near mint ", "Near Mint"),
        ("lightly played ", "Lightly Played"),
        ("moderately played ", "Moderately Played"),
        ("heavily played ", "Heavily Played"),
        ("damaged ", "Damaged"),
    ):
        if key.startswith(prefix):
            return canonical
    return text


def normalize_finish(value: str | None) -> str | None:
    text = normalize_space(value)
    if not text:
        return None
    key = _lookup_key(text)
    if "etched" in key and "foil" in key:
        return "Foil Etched"
    return _FINISH_ALIASES.get(key, text)


def normalize_listing(listing: Listing) -> Listing:
    """Return a normalized copy without changing adapter-specific objects."""
    currency = normalize_space(listing.currency).upper() or None
    return replace(
        listing,
        card_name=normalize_space(listing.card_name),
        set_name=normalize_space(listing.set_name) or None,
        set_code=(normalize_space(listing.set_code).upper() or None),
        collector_number=normalize_space(listing.collector_number) or None,
        language=normalize_language(listing.language),
        condition=normalize_condition(listing.condition),
        finish=normalize_finish(listing.finish),
        style=normalize_space(listing.style) or None,
        currency=currency,
        url=safe_http_url(listing.url),
        image_url=safe_http_url(listing.image_url),
        sku=normalize_space(listing.sku) or None,
        scryfall_id=normalize_space(listing.scryfall_id) or None,
    )


def normalize_listing_dict(row: dict) -> dict:
    out = dict(row)
    out["store"] = normalize_space(out.get("store"))
    out["card_name"] = normalize_space(out.get("card_name"))
    out["set_name"] = normalize_space(out.get("set_name")) or None
    out["set_code"] = normalize_space(out.get("set_code")).upper() or None
    out["collector_number"] = normalize_space(out.get("collector_number")) or None
    out["language"] = normalize_language(out.get("language"))
    out["condition"] = normalize_condition(out.get("condition"))
    out["finish"] = normalize_finish(out.get("finish"))
    out["style"] = normalize_space(out.get("style")) or None
    out["currency"] = normalize_space(out.get("currency")).upper() or None
    out["url"] = safe_http_url(out.get("url"))
    out["image_url"] = safe_http_url(out.get("image_url"))
    out["sku"] = normalize_space(out.get("sku")) or None
    out["scryfall_id"] = normalize_space(out.get("scryfall_id")) or None
    return out


def _field(row, name):
    return getattr(row, name) if isinstance(row, Listing) else row.get(name)


def listing_identity_key(row) -> str:
    """Stable per-store listing identity used to remove pagination duplicates."""
    store = normalize_card_search_text(_field(row, "store"))
    variant_id = _field(row, "variant_id")
    sku = normalize_space(_field(row, "sku"))
    product_id = _field(row, "product_id")
    url = safe_http_url(_field(row, "url"))

    if variant_id not in (None, ""):
        return f"{store}|variant:{variant_id}"
    if sku:
        return f"{store}|sku:{sku.casefold()}"

    attributes = "|".join(
        normalize_card_search_text(_field(row, name))
        for name in (
            "card_name",
            "set_name",
            "set_code",
            "collector_number",
            "language",
            "condition",
            "finish",
            "style",
            "currency",
        )
    )
    price = str(_field(row, "price") or "")
    if product_id not in (None, ""):
        return f"{store}|product:{product_id}|{attributes}|{price}"
    if url:
        return f"{store}|url:{url}|{attributes}|{price}"
    return f"{store}|attrs:{attributes}|{price}"


def _listing_score(row) -> int:
    fields = (
        "set_name", "set_code", "collector_number", "language", "condition",
        "finish", "style", "price", "stock", "url", "image_url", "product_id",
        "variant_id", "sku", "scryfall_id",
    )
    return sum(_field(row, field) not in (None, "") for field in fields)


def _merged_listing(current: Listing, incoming: Listing) -> Listing:
    preferred, other = (incoming, current) if _listing_score(incoming) > _listing_score(current) else (current, incoming)
    values = {}
    for name in Listing.__dataclass_fields__:
        if name == "raw":
            values[name] = preferred.raw or other.raw
            continue
        value = getattr(preferred, name)
        if value in (None, ""):
            value = getattr(other, name)
        values[name] = value
    stocks = [s for s in (current.stock, incoming.stock) if isinstance(s, int)]
    if stocks:
        values["stock"] = max(stocks)
    values["available"] = bool(current.available or incoming.available)
    return Listing(**values)


def dedupe_listings(rows: Iterable[Listing]) -> list[Listing]:
    unique: dict[str, Listing] = {}
    order: list[str] = []
    for raw in rows:
        row = normalize_listing(raw)
        key = listing_identity_key(row)
        if key not in unique:
            unique[key] = row
            order.append(key)
        else:
            unique[key] = _merged_listing(unique[key], row)
    return [unique[key] for key in order]


def dedupe_listing_dicts(rows: Iterable[dict]) -> list[dict]:
    unique: dict[str, dict] = {}
    order: list[str] = []
    for raw in rows:
        row = normalize_listing_dict(raw)
        key = listing_identity_key(row)
        if key not in unique:
            unique[key] = row
            order.append(key)
            continue
        current = unique[key]
        preferred, other = (row, current) if _listing_score(row) > _listing_score(current) else (current, row)
        merged = dict(preferred)
        for field, value in other.items():
            if merged.get(field) in (None, "") and value not in (None, ""):
                merged[field] = value
        stocks = [s for s in (current.get("stock"), row.get("stock")) if isinstance(s, int)]
        if stocks:
            merged["stock"] = max(stocks)
        merged["available"] = bool(current.get("available") or row.get("available"))
        unique[key] = merged
    return [unique[key] for key in order]
