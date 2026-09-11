from functools import lru_cache
from .http import HttpClient


class ScryfallService:
    BASE = "https://api.scryfall.com"

    def __init__(self, http: HttpClient | None = None):
        self.http = http or HttpClient()

    @lru_cache(maxsize=512)
    def exact_card(self, name: str) -> dict | None:
        try:
            return self.http.get(f"{self.BASE}/cards/named", params={"exact": name}).json()
        except Exception:
            return None

    def printing(self, name: str, set_code: str | None, collector_number: str | None) -> dict | None:
        if not set_code or not collector_number:
            return None
        try:
            data = self.http.get(f"{self.BASE}/cards/{set_code.lower()}/{collector_number}").json()
            if (data.get("name") or "").casefold() == name.casefold():
                return data
        except Exception:
            return None
        return None
