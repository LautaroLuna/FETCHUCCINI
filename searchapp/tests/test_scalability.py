from unittest import TestCase

from django.conf import settings
from django.core.cache import cache
from django.http import HttpResponse
from django.test import RequestFactory

from searchapp import views
from searchapp.version import __version__
from searchapp.middleware import RequestObservabilityMiddleware
from searchapp.services.cache_runtime import cache_health
from searchapp.services.metrics import metrics_snapshot, record_store_result


class ScalabilityContractTests(TestCase):
    def setUp(self):
        cache.clear()

    def test_version_and_cache_backend_are_exposed(self):
        self.assertEqual(settings.FETCHUCCINI_VERSION, __version__)
        self.assertIn(settings.FETCHUCCINI_CACHE_BACKEND, {"file", "redis"})
        status = cache_health(force=True)
        self.assertEqual(status["backend"], settings.FETCHUCCINI_CACHE_BACKEND)
        self.assertIn("ok", status)

    def test_store_metrics_are_aggregated_without_breaking_searches(self):
        record_store_result("test-store", elapsed_ms=120, success=True, source="live", count=2)
        record_store_result("test-store", elapsed_ms=0, success=True, source="cache", count=2)
        snapshot = metrics_snapshot(["test-store"])["stores"]["test-store"]
        self.assertEqual(snapshot["requests"], 2)
        self.assertEqual(snapshot["cache_hits"], 1)
        self.assertEqual(snapshot["results"], 4)
        self.assertEqual(snapshot["errors"], 0)

    def test_refresh_lock_key_uses_normalized_card_name(self):
        self.assertEqual(
            views._store_refresh_lock_key("Glóin the Mighty", "pirulo"),
            views._store_refresh_lock_key("Gloin the Mighty", "pirulo"),
        )

    def test_observability_middleware_adds_request_id_version_and_timing(self):
        request = RequestFactory().get("/api/search/cache/?q=Lightning+Bolt")
        middleware = RequestObservabilityMiddleware(lambda _request: HttpResponse("ok"))
        response = middleware(request)
        self.assertTrue(response["X-Request-ID"])
        self.assertEqual(response["X-Fetchuccini-Version"], __version__)
        self.assertIn("app;dur=", response["Server-Timing"])

    def test_observability_keeps_safe_incoming_request_id(self):
        request = RequestFactory().get("/health/", HTTP_X_REQUEST_ID="railway-check-123")
        middleware = RequestObservabilityMiddleware(lambda _request: HttpResponse("ok"))
        response = middleware(request)
        self.assertEqual(response["X-Request-ID"], "railway-check-123")

    def test_health_exposes_operational_scalability_fields(self):
        import json

        basic = views.health(RequestFactory().get("/health/"))
        basic_data = json.loads(basic.content)
        self.assertNotIn("metrics", basic_data)
        self.assertTrue(basic_data["metrics_available"])

        response = views.health(RequestFactory().get("/health/?details=1"))
        data = json.loads(response.content)
        self.assertEqual(data["version"], __version__)
        self.assertIn("cache", data)
        self.assertIn("concurrency", data)
        self.assertIn("metrics", data)
        self.assertIn("mercadia_catalog_freshness", data)
