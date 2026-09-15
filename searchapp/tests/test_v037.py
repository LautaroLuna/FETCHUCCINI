from unittest import TestCase

from django.test import RequestFactory

from searchapp import views
from searchapp.services.aggregator import SearchAggregator
from searchapp.services.http import HttpClient, SearchBudgetExceeded
from searchapp.services.store_registry import STORE_REGISTRY


class V037RegressionTests(TestCase):
    def test_empty_store_list_means_no_stores(self):
        rows, runs = SearchAggregator().search("Lightning Bolt", [])
        self.assertEqual(rows, [])
        self.assertEqual(runs, [])

    def test_query_requires_at_least_two_characters(self):
        query, response = views._validate_query(RequestFactory().get("/api/search/store/?q=a"))
        self.assertIsNone(query)
        self.assertEqual(response.status_code, 400)

    def test_registry_is_single_source_for_all_current_stores(self):
        self.assertEqual(len(STORE_REGISTRY), 7)
        self.assertIn("mercadia", STORE_REGISTRY)
        self.assertGreater(STORE_REGISTRY["magicdealers"].policy.fresh_cache_seconds, 5 * 60)
        self.assertEqual(STORE_REGISTRY["batikueva"].policy.max_pages, 6)
        self.assertLessEqual(STORE_REGISTRY["batikueva"].policy.deadline_seconds, 6)

    def test_http_budget_caps_logical_requests(self):
        client = HttpClient()
        client.configure_budget(deadline_seconds=10, max_requests=2)
        client.reserve_request()
        client.reserve_request()
        with self.assertRaises(SearchBudgetExceeded):
            client.reserve_request()
