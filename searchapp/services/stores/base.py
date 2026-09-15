from abc import ABC, abstractmethod

from ..http import HttpClient
from ..models import Listing


class StoreAdapter(ABC):
    key = "base"
    name = "Base"

    def __init__(self, http: HttpClient | None = None):
        self.http = http or HttpClient()
        self.partial = False
        self.partial_error: str | None = None
        self.policy = None

    def configure_policy(self, policy) -> None:
        self.policy = policy
        self.http.configure_budget(
            deadline_seconds=policy.deadline_seconds,
            max_requests=policy.max_requests,
            connect_timeout_seconds=policy.connect_timeout_seconds,
            read_timeout_seconds=policy.read_timeout_seconds,
        )

    def mark_partial(self, error: Exception | str | None = None) -> None:
        self.partial = True
        if error:
            if isinstance(error, Exception):
                self.partial_error = f"{type(error).__name__}: {error}"
            else:
                self.partial_error = str(error)

    @abstractmethod
    def search(self, card_name: str) -> list[Listing]:
        raise NotImplementedError
