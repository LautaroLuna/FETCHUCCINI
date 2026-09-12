from unittest import TestCase
from django.core.cache import cache

from searchapp.services.resilience import (
    CIRCUIT_FAILURE_THRESHOLD,
    circuit_is_open,
    circuit_record_failure,
    circuit_record_success,
)


class CircuitBreakerTests(TestCase):
    def setUp(self):
        cache.clear()

    def test_opens_after_repeated_failures_and_recovers_on_success(self):
        for _ in range(CIRCUIT_FAILURE_THRESHOLD):
            circuit_record_failure("test-store", "boom")
        is_open, retry_after = circuit_is_open("test-store")
        self.assertTrue(is_open)
        self.assertGreater(retry_after, 0)
        circuit_record_success("test-store")
        self.assertFalse(circuit_is_open("test-store")[0])
