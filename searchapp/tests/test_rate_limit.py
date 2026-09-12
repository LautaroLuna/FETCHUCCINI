from unittest import TestCase
from django.core.cache import cache
from django.test import RequestFactory

from searchapp import views


class RateLimitTests(TestCase):
    def setUp(self):
        cache.clear()
        self.factory = RequestFactory()

    def test_rate_limit_returns_429_after_limit(self):
        original = views.RATE_LIMITS["search_all"]
        views.RATE_LIMITS["search_all"] = (2, 60)
        try:
            request = self.factory.get("/api/search/?q=Lightning+Bolt", REMOTE_ADDR="127.0.0.1")
            self.assertIsNone(views._rate_limit_response(request, "search_all"))
            self.assertIsNone(views._rate_limit_response(request, "search_all"))
            response = views._rate_limit_response(request, "search_all")
            self.assertEqual(response.status_code, 429)
            self.assertIn("Retry-After", response)
        finally:
            views.RATE_LIMITS["search_all"] = original
