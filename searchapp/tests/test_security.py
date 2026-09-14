from unittest import TestCase

from django.http import HttpResponse
from django.test import RequestFactory, override_settings

from searchapp import views
from searchapp.middleware import ResponseSecurityHeadersMiddleware


class SecurityContractTests(TestCase):
    def test_security_middleware_sets_public_headers(self):
        request = RequestFactory().get("/")
        middleware = ResponseSecurityHeadersMiddleware(lambda _request: HttpResponse("ok"))
        response = middleware(request)
        self.assertIn("Content-Security-Policy", response)
        self.assertIn("Permissions-Policy", response)
        self.assertEqual(response["Referrer-Policy"], "strict-origin-when-cross-origin")
        self.assertIn("object-src 'none'", response["Content-Security-Policy"])

    @override_settings(FETCHUCCINI_TRUST_PROXY_HEADERS=True)
    def test_rate_limit_prefers_railway_real_ip(self):
        request = RequestFactory().get(
            "/api/search/?q=Lightning+Bolt",
            HTTP_X_REAL_IP="203.0.113.21",
            HTTP_X_FORWARDED_FOR="198.51.100.5, 10.0.0.9",
            REMOTE_ADDR="10.0.0.9",
        )
        self.assertEqual(views._client_ip(request), "203.0.113.21")

    @override_settings(FETCHUCCINI_TRUST_PROXY_HEADERS=True)
    def test_rate_limit_falls_back_to_original_forwarded_client(self):
        request = RequestFactory().get(
            "/api/search/?q=Lightning+Bolt",
            HTTP_X_FORWARDED_FOR="203.0.113.15, 10.0.0.9",
            REMOTE_ADDR="10.0.0.9",
        )
        self.assertEqual(views._client_ip(request), "203.0.113.15")


    @override_settings(FETCHUCCINI_TRUST_PROXY_HEADERS=False)
    def test_direct_client_cannot_spoof_forwarded_rate_limit_ip(self):
        request = RequestFactory().get(
            "/api/search/?q=Lightning+Bolt",
            HTTP_X_REAL_IP="203.0.113.21",
            HTTP_X_FORWARDED_FOR="198.51.100.5",
            REMOTE_ADDR="127.0.0.1",
        )
        self.assertEqual(views._client_ip(request), "127.0.0.1")

    def test_store_cache_key_is_accent_and_punctuation_insensitive(self):
        self.assertEqual(
            views._store_cache_keys("Glóin the Mighty", "magicdealers"),
            views._store_cache_keys("Gloin the Mighty", "magicdealers"),
        )
        self.assertEqual(
            views._store_cache_keys("Urza’s Saga", "pirulo"),
            views._store_cache_keys("Urza's Saga", "pirulo"),
        )
