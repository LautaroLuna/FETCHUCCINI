import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


class HttpClient:
    def __init__(self, timeout: int = 12):
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "MTGPriceFinder/0.1 (+local development; respectful low-rate requests)",
            "Accept-Language": "en-US,en;q=0.9,es;q=0.8",
        })
        retry = Retry(
            total=2,
            backoff_factor=0.35,
            status_forcelist=(429, 500, 502, 503, 504),
            allowed_methods=frozenset({"GET", "POST"}),
        )
        self.session.mount("https://", HTTPAdapter(max_retries=retry))

    def get(self, url, **kwargs):
        kwargs.setdefault("timeout", self.timeout)
        response = self.session.get(url, **kwargs)
        response.raise_for_status()
        return response

    def post(self, url, **kwargs):
        kwargs.setdefault("timeout", self.timeout)
        response = self.session.post(url, **kwargs)
        response.raise_for_status()
        return response
