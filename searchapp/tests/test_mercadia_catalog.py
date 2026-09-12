import json
import tempfile
from pathlib import Path
from unittest import TestCase
from django.test import override_settings

from searchapp.services import mercadia_catalog


class MercadiaCatalogIndexTests(TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        mercadia_catalog._CACHE_DATA = None
        mercadia_catalog._CACHE_MTIME = None
        mercadia_catalog._CACHE_INDEX = {}
        mercadia_catalog._CACHE_NAMES = []

    def tearDown(self):
        self.tmp.cleanup()

    def _write_catalog(self):
        path = Path(self.tmp.name) / "mercadia_catalog.json"
        payload = {
            "version": 1,
            "synced_at": 1,
            "results": [
                {"store":"Mercadia","card_name":"Lightning Bolt","available":True,"stock":2,"price":"100"},
                {"store":"Mercadia","card_name":"Lightning Bolt","available":True,"stock":1,"price":"120"},
                {"store":"Mercadia","card_name":"Lightning Greaves","available":True,"stock":3,"price":"300"},
                {"store":"Mercadia","card_name":"Lightning Strike","available":False,"stock":0,"price":"50"},
            ],
        }
        path.write_text(json.dumps(payload), encoding="utf-8")

    def test_exact_and_prefix_use_index_and_keep_stock_only(self):
        self._write_catalog()
        with override_settings(MERCADIA_CATALOG_DIR=Path(self.tmp.name)):
            exact, _ = mercadia_catalog.search_catalog("Lightning Bolt")
            prefix, _ = mercadia_catalog.search_catalog("Lightning")
        self.assertEqual(len(exact), 2)
        self.assertEqual([row["card_name"] for row in prefix], [
            "Lightning Bolt", "Lightning Bolt", "Lightning Greaves"
        ])
        self.assertIn("lightning bolt", mercadia_catalog._CACHE_INDEX)
