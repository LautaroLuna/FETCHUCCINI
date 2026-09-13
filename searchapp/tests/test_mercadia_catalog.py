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


class MercadiaCatalogSafetyTests(TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        mercadia_catalog._CACHE_DATA = None
        mercadia_catalog._CACHE_MTIME = None
        mercadia_catalog._CACHE_INDEX = {}
        mercadia_catalog._CACHE_NAMES = []

    def tearDown(self):
        self.tmp.cleanup()

    def _write_existing(self, count=100, synced_at=None):
        path = Path(self.tmp.name) / "mercadia_catalog.json"
        payload = {
            "version": 2,
            "synced_at": synced_at if synced_at is not None else 1000,
            "results": [
                {
                    "store": "Mercadia",
                    "card_name": f"Card {i}",
                    "available": True,
                    "stock": 1,
                    "price": str(i + 1),
                    "currency": "ARS",
                    "sku": f"SKU-{i}",
                }
                for i in range(count)
            ],
        }
        path.write_text(json.dumps(payload), encoding="utf-8")
        return path

    def test_rejects_suspiciously_small_sync_and_preserves_previous_catalog(self):
        path = self._write_existing(count=100)
        previous = path.read_text(encoding="utf-8")
        with override_settings(
            MERCADIA_CATALOG_DIR=Path(self.tmp.name),
            MERCADIA_CATALOG_MIN_PUBLISH_COUNT=0,
            MERCADIA_CATALOG_MIN_PUBLISH_RATIO=0.65,
        ):
            mercadia_catalog.begin_sync("small-sync")
            mercadia_catalog.append_batch("small-sync", [
                {
                    "card_name": f"New {i}",
                    "available": True,
                    "stock": 1,
                    "price": "10",
                    "currency": "ARS",
                    "sku": f"NEW-{i}",
                }
                for i in range(10)
            ])
            with self.assertRaises(ValueError):
                mercadia_catalog.finish_sync("small-sync")
        self.assertEqual(path.read_text(encoding="utf-8"), previous)

    def test_catalog_freshness_levels(self):
        import time
        now = time.time()
        with override_settings(
            MERCADIA_CATALOG_DIR=Path(self.tmp.name),
            MERCADIA_CATALOG_WARN_AGE_SECONDS=100,
            MERCADIA_CATALOG_STALE_AGE_SECONDS=200,
        ):
            self._write_existing(count=2, synced_at=now - 50)
            mercadia_catalog._CACHE_DATA = None
            self.assertEqual(mercadia_catalog.catalog_status()["freshness"], "fresh")

            self._write_existing(count=2, synced_at=now - 150)
            mercadia_catalog._CACHE_DATA = None
            self.assertEqual(mercadia_catalog.catalog_status()["freshness"], "warning")

            self._write_existing(count=2, synced_at=now - 250)
            mercadia_catalog._CACHE_DATA = None
            self.assertEqual(mercadia_catalog.catalog_status()["freshness"], "stale")

    def test_old_staging_files_are_cleaned_on_new_sync(self):
        import os
        import time
        stale = Path(self.tmp.name) / "mercadia_catalog.old.jsonl"
        stale.write_text("{}\n", encoding="utf-8")
        old = time.time() - 10_000
        os.utime(stale, (old, old))
        with override_settings(
            MERCADIA_CATALOG_DIR=Path(self.tmp.name),
            MERCADIA_STAGING_MAX_AGE_SECONDS=3600,
        ):
            result = mercadia_catalog.begin_sync("new-sync")
        self.assertFalse(stale.exists())
        self.assertGreaterEqual(result["stale_staging_removed"], 1)
