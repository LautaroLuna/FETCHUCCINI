import html
import json
import re
import unicodedata
from decimal import Decimal, InvalidOperation
from urllib.parse import urljoin


def first(value, default=None):
    if isinstance(value, list):
        return value[0] if value else default
    return value if value is not None else default


def to_decimal(value) -> Decimal | None:
    if value is None or value == "":
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        return None


def parse_ars(text: str | None) -> Decimal | None:
    if not text:
        return None
    cleaned = re.sub(r"[^0-9,.-]", "", text)
    if not cleaned:
        return None
    if "," in cleaned:
        cleaned = cleaned.replace(".", "").replace(",", ".")
    try:
        return Decimal(cleaned)
    except InvalidOperation:
        return None


def as_int(value) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def normalize_space(text: str | None) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


def strip_diacritics(text: str | None) -> str:
    """Return text without combining accent marks, preserving readable casing.

    Stores do not always keep MTG card names exactly as Scryfall writes them.
    For example, Scryfall uses ``Glóin the Mighty`` while some shops publish
    ``Gloin the Mighty``.  We keep the canonical spelling for the UI, but use
    this folded form for matching/search fallbacks.
    """
    normalized = unicodedata.normalize("NFKD", str(text or ""))
    return "".join(ch for ch in normalized if not unicodedata.combining(ch))


def normalize_card_search_text(text: str | None) -> str:
    """Normalize card-name text for accent-insensitive comparisons."""
    return normalize_space(strip_diacritics(text)).casefold()


def search_query_variants(query: str | None) -> list[str]:
    """Return the canonical query plus an accent-folded fallback when useful."""
    original = normalize_space(query)
    if not original:
        return []
    folded = normalize_space(strip_diacritics(original))
    variants = [original]
    if folded and folded.casefold() != original.casefold():
        variants.append(folded)
    return variants


def exactish_card_name(candidate: str | None, query: str) -> bool:
    """Match card names by prefix, case- and accent-insensitively.

    Fetchuccini treats the search box as a prefix search: "lightning" may
    return Lightning Bolt, Lightning Axe, Lightning Helix, etc. Exact searches
    still work because an exact name is naturally also a prefix of itself.

    Accent folding is intentional because shops frequently publish MTG names
    without the diacritics used by Scryfall (e.g. ``Glóin`` vs ``Gloin``).
    """
    c = normalize_card_search_text(candidate)
    q = normalize_card_search_text(query)
    return bool(c and q and c.startswith(q))


def json_attr(value: str | None):
    if not value:
        return None
    try:
        return json.loads(html.unescape(value))
    except (json.JSONDecodeError, TypeError):
        return None


def absolute(base: str, url: str | None) -> str | None:
    return urljoin(base, url) if url else None
