import html
import json
import re
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


def exactish_card_name(candidate: str | None, query: str) -> bool:
    c = normalize_space(candidate).casefold()
    q = normalize_space(query).casefold()
    return c == q or c.startswith(q + " (") or c.startswith(q + " - ") or c.startswith(q + " [")


def json_attr(value: str | None):
    if not value:
        return None
    try:
        return json.loads(html.unescape(value))
    except (json.JSONDecodeError, TypeError):
        return None


def absolute(base: str, url: str | None) -> str | None:
    return urljoin(base, url) if url else None
