import html
import json
import re
import unicodedata
from decimal import Decimal, InvalidOperation
from urllib.parse import urljoin, urlparse


_APOSTROPHES_RE = re.compile(r"[\u2018\u2019\u201a\u201b\u2032\u02bc\u0060\u00b4]")
_DASHES_RE = re.compile(r"[\u2010\u2011\u2012\u2013\u2014\u2015\u2212]")
_ZERO_WIDTH_RE = re.compile(r"[\u200b\u200c\u200d\ufeff]")
_SPLIT_RE = re.compile(r"\s*/+\s*")


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
    """Return text without combining accent marks, preserving readable casing."""
    normalized = unicodedata.normalize("NFKD", str(text or ""))
    return "".join(ch for ch in normalized if not unicodedata.combining(ch))


def normalize_card_punctuation(text: str | None) -> str:
    """Normalize punctuation variants commonly seen in MTG storefront names.

    Storefronts frequently replace curly apostrophes/dashes or write split-card
    separators differently.  Keep this function display-friendly so it can also
    be used to generate safe fallback query variants.
    """
    value = unicodedata.normalize("NFKC", str(text or ""))
    value = _ZERO_WIDTH_RE.sub("", value)
    value = _APOSTROPHES_RE.sub("'", value)
    value = _DASHES_RE.sub("-", value)
    value = value.replace("／", "/")
    value = _SPLIT_RE.sub(" // ", value)
    return normalize_space(value)


def normalize_card_search_text(text: str | None) -> str:
    """Canonical comparison/cache key for MTG card names.

    The key intentionally ignores diacritics and harmless punctuation
    differences while preserving the split-card separator. Examples that map to
    the same key include ``Glóin``/``Gloin`` and ``Urza’s``/``Urza's``.
    """
    value = strip_diacritics(normalize_card_punctuation(text)).casefold()
    value = value.replace("'", "")
    value = re.sub(r"\s*//\s*", " // ", value)
    value = re.sub(r"[-_.:,;!?()\[\]{}\"“”]+", " ", value)
    value = re.sub(r"[^\w/&+*# //]+", " ", value, flags=re.UNICODE)
    return normalize_space(value)


def _append_unique(values: list[str], value: str | None) -> None:
    value = normalize_space(value)
    if not value:
        return
    key = value.casefold()
    if all(existing.casefold() != key for existing in values):
        values.append(value)


def search_query_variants(query: str | None) -> list[str]:
    """Return increasingly tolerant storefront query variants.

    The canonical Scryfall spelling is always attempted first.  Fallbacks are
    only useful when the previous store query yielded zero purchasable rows.
    This keeps ordinary searches to a single request while covering accents,
    curly apostrophes, Unicode dashes and split-card separators.
    """
    original = normalize_space(query)
    if not original:
        return []

    variants: list[str] = []
    _append_unique(variants, original)

    punctuation = normalize_card_punctuation(original)
    _append_unique(variants, punctuation)

    folded = normalize_space(strip_diacritics(punctuation))
    _append_unique(variants, folded)

    # Some shop search engines index split/DFC cards under a single slash or
    # only under the front face. These variants are attempted last.
    if " // " in punctuation:
        _append_unique(variants, punctuation.replace(" // ", " / "))
        front = punctuation.split(" // ", 1)[0]
        _append_unique(variants, front)
        _append_unique(variants, strip_diacritics(front))

    return variants[:6]


def exactish_card_name(candidate: str | None, query: str) -> bool:
    """Match card names by prefix using MTG-aware normalization.

    Prefix behavior is deliberate: ``lightning`` may return Lightning Bolt,
    Lightning Axe, etc.  For split cards, a storefront that exposes only the
    exact front-face name is also accepted after the full-name search fallback.
    """
    c = normalize_card_search_text(candidate)
    q = normalize_card_search_text(query)
    if not c or not q:
        return False
    if c.startswith(q):
        return True
    if " // " in q:
        front = q.split(" // ", 1)[0]
        return c == front
    return False


def safe_http_url(value: str | None) -> str | None:
    """Return only absolute http(s) URLs suitable for href/src attributes."""
    text = normalize_space(value)
    if not text:
        return None
    try:
        parsed = urlparse(text)
    except ValueError:
        return None
    if parsed.scheme.casefold() not in {"http", "https"} or not parsed.netloc:
        return None
    return text


def json_attr(value: str | None):
    if not value:
        return None
    try:
        return json.loads(html.unescape(value))
    except (json.JSONDecodeError, TypeError):
        return None


def absolute(base: str, url: str | None) -> str | None:
    return urljoin(base, url) if url else None
