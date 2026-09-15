from __future__ import annotations

import time

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from searchapp.version import __version__


class SearchBudgetExceeded(requests.RequestException):
    """Raised when one store exceeds its request/time budget."""


class HttpClient:
    def __init__(self, timeout: int | float | tuple = 12):
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": f"Fetchuccini/{__version__} (+public MTG price comparison; respectful low-rate requests)",
            "Accept-Language": "en-US,en;q=0.9,es;q=0.8",
        })
        retry = Retry(
            # One transport retry is enough for transient 429/5xx without
            # multiplying a store deadline into tens of seconds.
            total=1,
            backoff_factor=0.35,
            status_forcelist=(429, 500, 502, 503, 504),
            allowed_methods=frozenset({"GET", "POST"}),
            respect_retry_after_header=True,
        )
        self.session.mount("https://", HTTPAdapter(max_retries=retry))

        self._budget_deadline: float | None = None
        self._budget_max_requests: int | None = None
        self._budget_requests = 0
        self._budget_connect_timeout: float | None = None
        self._budget_read_timeout: float | None = None

    def configure_budget(
        self,
        *,
        deadline_seconds: float | None = None,
        max_requests: int | None = None,
        connect_timeout_seconds: float | None = None,
        read_timeout_seconds: float | None = None,
    ) -> None:
        self._budget_deadline = (
            time.monotonic() + max(0.1, float(deadline_seconds))
            if deadline_seconds is not None
            else None
        )
        self._budget_max_requests = max(1, int(max_requests)) if max_requests is not None else None
        self._budget_requests = 0
        self._budget_connect_timeout = (
            max(0.1, float(connect_timeout_seconds))
            if connect_timeout_seconds is not None
            else None
        )
        self._budget_read_timeout = (
            max(0.1, float(read_timeout_seconds))
            if read_timeout_seconds is not None
            else None
        )

    @property
    def requests_made(self) -> int:
        return self._budget_requests

    def remaining_seconds(self) -> float | None:
        if self._budget_deadline is None:
            return None
        return max(0.0, self._budget_deadline - time.monotonic())

    def reserve_request(self, requested_timeout=None):
        """Consume one logical request from the active store budget.

        This is public so adapters that intentionally bypass this Session (for
        example MagicDealers' fresh-connection strategy) still participate in
        the same deadline/request budget.
        """
        remaining = self.remaining_seconds()
        if remaining is not None and remaining <= 0:
            raise SearchBudgetExceeded("se agotó el tiempo máximo de búsqueda para la tienda")

        if self._budget_max_requests is not None and self._budget_requests >= self._budget_max_requests:
            raise SearchBudgetExceeded(
                f"se alcanzó el máximo de {self._budget_max_requests} requests para la tienda"
            )
        self._budget_requests += 1

        timeout = requested_timeout if requested_timeout is not None else self.timeout
        if self._budget_connect_timeout is not None or self._budget_read_timeout is not None:
            connect = self._budget_connect_timeout or self._coerce_timeout_part(timeout, 0, 3.0)
            read = self._budget_read_timeout or self._coerce_timeout_part(timeout, 1, 9.0)
            if remaining is not None:
                # Keep enough room for exception handling and response parsing.
                read = min(read, max(0.2, remaining))
                connect = min(connect, max(0.2, remaining))
            return (connect, read)

        if remaining is not None:
            if isinstance(timeout, tuple):
                connect, read = timeout
                return (min(float(connect), remaining), min(float(read), remaining))
            return min(float(timeout), remaining)
        return timeout

    @staticmethod
    def _coerce_timeout_part(timeout, index: int, fallback: float) -> float:
        try:
            if isinstance(timeout, tuple):
                return max(0.1, float(timeout[index]))
            return max(0.1, float(timeout))
        except (TypeError, ValueError, IndexError):
            return fallback

    def get(self, url, **kwargs):
        requested_timeout = kwargs.pop("timeout", None)
        kwargs["timeout"] = self.reserve_request(requested_timeout)
        response = self.session.get(url, **kwargs)
        response.raise_for_status()
        return response

    def post(self, url, **kwargs):
        requested_timeout = kwargs.pop("timeout", None)
        kwargs["timeout"] = self.reserve_request(requested_timeout)
        response = self.session.post(url, **kwargs)
        response.raise_for_status()
        return response
