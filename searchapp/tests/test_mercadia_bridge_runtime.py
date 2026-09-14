import importlib
import os
from unittest import TestCase
from unittest.mock import patch


class MercadiaBridgeRuntimeTests(TestCase):
    def setUp(self):
        self.sync = importlib.import_module("scripts.mercadia_catalog_sync")

    def test_duration_format(self):
        self.assertEqual(self.sync._duration(0), "0m 00s")
        self.assertEqual(self.sync._duration(125), "2m 05s")
        self.assertEqual(self.sync._duration(3661), "1h 01m 01s")

    def test_worker_env_is_clamped(self):
        with patch.dict(os.environ, {"TEST_WORKERS": "99"}):
            self.assertEqual(self.sync._env_int("TEST_WORKERS", 3, 1, 4), 4)
        with patch.dict(os.environ, {"TEST_WORKERS": "0"}):
            self.assertEqual(self.sync._env_int("TEST_WORKERS", 3, 1, 4), 1)
