from functools import lru_cache
from .http import HttpClient
from searchapp.version import __version__


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

    def autocomplete(self, query: str, limit: int = 12) -> list[str]:
        """Return canonical card-name suggestions from Scryfall.

        We keep this low-rate and cached at the Django view layer. Scryfall asks
        API clients to send an explicit User-Agent and Accept header.
        """
        query = (query or "").strip()
        if len(query) < 2:
            return []

        try:
            response = self.http.get(
                f"{self.BASE}/cards/autocomplete",
                params={"q": query},
                headers={
                    "User-Agent": f"Fetchuccini/{__version__} (MTG price comparison; https://github.com/LautaroLuna/FETCHUCCINI)",
                    "Accept": "application/json;q=0.9,*/*;q=0.8",
                },
            )
            data = response.json()
            names = data.get("data") or []
            return [str(name) for name in names[:max(1, min(int(limit), 20))] if name]
        except Exception:
            return []
