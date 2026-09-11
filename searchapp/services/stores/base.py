from abc import ABC, abstractmethod
from ..http import HttpClient
from ..models import Listing


class StoreAdapter(ABC):
    key = "base"
    name = "Base"

    def __init__(self, http: HttpClient | None = None):
        self.http = http or HttpClient()

    @abstractmethod
    def search(self, card_name: str) -> list[Listing]:
        raise NotImplementedError
